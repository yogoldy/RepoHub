"""The actual JS presentation must agree with independent diagnostic evidence."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from change_evidence import ChangeEvidence
from diagnostics import DiagnosticLog, read_events
from diagnostic_export import export_bundle

ROOT = Path(__file__).resolve().parents[1]


class ClarityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = DiagnosticLog(self.root / 'logs')
        self.evidence = ChangeEvidence(self.log)
        self.good = {'id': 'private-repo', 'name': 'Private repo', 'health': {'fresh': True},
                     'needs_backup': False, 'last_backup': {'archive': '/private/current', 'sha256': 'private-sha'},
                     'verification': {'state': 'matched', 'archive': '/private/current'},
                     'cloud': {'state': 'uploaded', 'archive': '/private/current'}}

    def tearDown(self):
        self.temp.cleanup()

    def render(self, repo, backup=None):
        script = """const p=require('./web/repo-status.js');
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
const before=JSON.stringify(input), old=p.view(input.repo,input.backup), next=p.present(input.repo,input.backup);
if(before!==JSON.stringify(input)||old.phase!==next.phase||old.ready!==next.ready||old.percent!==next.percent)throw Error('Policy mutated');
console.log(JSON.stringify(next));"""
        return json.loads(subprocess.check_output(['node', '-e', script], cwd=ROOT,
                          input=json.dumps({'repo': repo, 'backup': backup or {}}), text=True))

    def report(self, repo, backup=None, freshness='current'):
        observed = {'repos': [repo], 'backup': backup or {}}
        observation = self.evidence.observe_status(observed)
        displayed = copy.deepcopy(repo)
        if freshness != 'current':
            displayed['health'] = {'fresh': False}
        rendered = self.render(displayed, backup)
        row = {'repo_id': repo['id'], 'phase': rendered['phase'], 'ready': rendered['ready'],
               'category': rendered['category'], 'display_label': rendered['label'],
               'display_headline': rendered['headline']}
        payload = {'surface': 'menu', 'native': False, 'client_id': 'c' * 24,
                   'observation_id': observation, 'policy_version': 'status-clarity-2',
                   'client_freshness': freshness, 'rows': [row]}
        self.evidence.presentation(payload)
        return payload

    def test_actual_js_mapping_preserves_policy_and_matches_evidence(self):
        cases = [(self.good, {})]
        for state in ['checking', 'changing', 'error']:
            row = copy.deepcopy(self.good)
            row['verification'] = {'state': state, 'error': 'local error' if state == 'error' else None}
            cases.append((row, {}))
        for state in ['pending', 'uploading', 'unknown', 'error']:
            row = copy.deepcopy(self.good)
            row['cloud']['state'] = state
            row['cloud']['percent'] = 100
            cases.append((row, {}))
            wrong = copy.deepcopy(row)
            wrong['cloud']['archive'] = '/private/old'
            cases.append((wrong, {}))
        for counts in [{'repo_files': 1}, {'git_data': 1}, {'finder_metadata': 1}, {}]:
            row = copy.deepcopy(self.good)
            row['needs_backup'] = True
            row['verification'].update(state='different', changes={'counts': counts})
            cases.append((row, {}))
        first = copy.deepcopy(self.good)
        first.update(needs_backup=True, last_backup=None)
        cases.append((first, {}))
        finder = copy.deepcopy(self.good)
        finder['verification'].update(state='different', ignored_finder_only=True, backup_required=False)
        cases.append((finder, {}))
        cases.append((self.good, {'running': True, 'current_repo_id': self.good['id']}))
        stale = copy.deepcopy(self.good)
        stale['health']['fresh'] = False
        cases.append((stale, {}))
        for row, backup in cases:
            with self.subTest(row=row, backup=backup):
                self.report(row, backup)
        for reason in ['request_failed', 'response_timeout', 'cache_expired']:
            self.report(self.good, freshness=reason)
        self.assertFalse([e for e in read_events(self.root/'logs')
                          if e['event'] == 'presentation_input_disagreement'])
        self.assertFalse(self.render(finder)['ready'], 'Finder exception cannot become strict green')
        finder_pending = copy.deepcopy(finder)
        finder_pending['needs_backup'] = True
        finder_pending['verification']['changes'] = {'counts': {'finder_metadata': 1}}
        self.assertNotEqual(self.render(finder_pending)['label'], 'Edits confirmed')


    def test_only_labels_require_complete_current_comparison(self):
        for finder, git, expected in [
            (1, 0, 'Only Finder metadata changed'),
            (0, 1, 'Only Git data changed'),
            (1, 1, 'Only Git and Finder metadata changed'),
        ]:
            row = copy.deepcopy(self.good)
            row['needs_backup'] = True
            counts = {'repo_files': 0, 'git_data': git, 'finder_metadata': finder}
            row['verification'].update(state='different', changes={'counts': counts})
            self.assertEqual(self.render(row)['label'], expected)
            self.report(row)
            for malformed in [{'git_data': git, 'finder_metadata': finder},
                              dict(counts, repo_files=1), dict(counts, repo_files=-1)]:
                row['verification']['changes']['counts'] = malformed
                self.assertFalse(self.render(row)['label'].startswith('Only '))
            row['verification']['changes']['counts'] = counts
            row['verification']['archive'] = '/private/old'
            self.assertFalse(self.render(row)['label'].startswith('Only '))
        self.assertFalse([e for e in read_events(self.root/'logs')
                          if e['event'] == 'presentation_input_disagreement'])

    def test_previous_presentation_version_keeps_its_original_wording(self):
        row = copy.deepcopy(self.good)
        row['needs_backup'] = True
        row['verification'].update(state='different', changes={'counts': {
            'repo_files': 0, 'git_data': 1, 'finder_metadata': 0}})
        payload = self.report(row)
        payload['policy_version'] = 'status-clarity-1'
        payload['rows'][0].update(display_label='Edits confirmed',
                                  display_headline='RepoHub confirmed edits.')
        self.evidence.presentation(payload)
        self.assertFalse([e for e in read_events(self.root/'logs')
                          if e['event'] == 'presentation_input_disagreement'])

    def test_wrong_category_sentence_and_false_green_are_detected(self):
        for changes in [{'category': 'failure'}, {'display_headline': 'RepoHub confirmed edits.'},
                        {'phase': 'ready', 'ready': True}]:
            row = copy.deepcopy(self.good)
            row['cloud']['state'] = 'unknown'
            payload = self.report(row)
            payload['rows'][0].update(changes)
            self.evidence.presentation(payload)
            events = list(read_events(self.root/'logs'))
            self.assertEqual(events[-1]['reason'], 'presentation_inputs_disagree')

    def test_untyped_version_category_and_headline_fail_closed(self):
        payload = self.report(self.good)
        for location, field in [('frame', 'policy_version'), ('row', 'category'), ('row', 'display_headline')]:
            for value in [[], {}, True, None, 'private unapproved prose']:
                bad = copy.deepcopy(payload)
                target = bad if location == 'frame' else bad['rows'][0]
                target[field] = value
                with self.assertRaises(ValueError):
                    self.evidence.presentation(bad)

    def test_new_export_fields_are_typed_and_never_copy_exception_prose(self):
        self.report(self.good)
        self.log.emit('ui_presented', category='private-name', display_headline='/Users/private/secret.env')
        bundle = export_bundle(self.root/'logs', self.root/'exports')
        shared = (bundle/'share/events.jsonl').read_text()
        rows = [json.loads(line) for line in shared.splitlines()]
        actual = next(e for e in rows if e.get('policy_version') == 'status-clarity-2' and e['event'] == 'ui_presented')
        self.assertEqual(actual['category'], 'backed_up')
        self.assertEqual(actual['display_headline'], 'Your files are backed up.')
        for text in ['private-name', '/Users/private', '/private/current', 'private-repo', 'private-sha']:
            self.assertNotIn(text, shared)
        self.assertNotIn('category', rows[-1])
        self.assertNotIn('display_headline', rows[-1])
