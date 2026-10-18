"""The actual JS presentation must agree with independent diagnostic evidence."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from change_evidence import ChangeEvidence, compact_timing_receipt, presentation_text, timing_receipt
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
const expectedPhase=old.phase==='background'?'ready':old.phase;
const expectedReady=old.ready||old.phase==='background';
if(before!==JSON.stringify(input)||expectedPhase!==next.phase||expectedReady!==next.ready||old.percent!==next.percent)throw Error('Unexpected policy change');
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
                   'observation_id': observation, 'policy_version': 'status-clarity-7',
                   'client_freshness': freshness, 'selected_repo_id': repo['id'], 'rows': [row]}
        row['timing'] = timing_receipt(self.evidence.snapshots[observation][repo['id']], freshness)
        row['card_timing'] = {**compact_timing_receipt(row['timing']), 'text_matches': True}
        row['detail_timing'] = {'receipt': row['timing'], 'text_matches': True}
        self.evidence.presentation(payload)
        return payload

    def test_waiting_copy_keeps_stale_evidence_non_green_and_recovers_without_backup(self):
        before = copy.deepcopy(self.good)
        stale = copy.deepcopy(self.good)
        stale['health'] = {'fresh': False, 'reasons': ['Repo checks stopped updating']}
        waiting = self.render(stale)
        self.assertEqual(waiting['phase'], 'stale')
        self.assertFalse(waiting['ready'])
        self.assertEqual(waiting['category'], 'status_unavailable')
        self.assertEqual(waiting['label'], 'Waiting for fresh checks')
        self.assertEqual(waiting['headline'], 'Waiting for fresh backup status.')
        self.assertIn('Rescan now', waiting['detail'])
        payload = self.report(stale)
        for version in range(1, 7):
            old = copy.deepcopy(payload)
            old['policy_version'] = f'status-clarity-{version}'
            facts = self.evidence.snapshots[old['observation_id']][stale['id']]
            old['rows'][0].update(presentation_text(facts, 'stale', old['policy_version']))
            if version < 6:
                old['rows'][0].pop('card_timing')
                old['rows'][0].pop('detail_timing')
            if version < 4:
                old.pop('selected_repo_id')
                old['rows'][0].pop('timing')
            self.evidence.presentation(old)
        self.report(self.good)
        self.assertTrue(self.render(self.good)['ready'])
        self.assertEqual(self.good, before)
        self.assertFalse([event for event in read_events(self.root/'logs')
                          if event['event'] == 'presentation_input_disagreement'])
        payload['rows'][0].update(phase='ready', ready=True, category='backed_up',
                                 display_label='Backed up', display_headline='Your files are backed up.')
        self.evidence.presentation(payload)
        self.assertTrue([event for event in read_events(self.root/'logs')
                         if event['event'] == 'presentation_input_disagreement'])

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
        self.assertTrue(self.render(finder)['ready'], 'Fresh Finder-only evidence allows the approved green display')
        finder_pending = copy.deepcopy(finder)
        finder_pending['needs_backup'] = True
        finder_pending['verification']['changes'] = {'counts': {'finder_metadata': 1}}
        self.assertNotEqual(self.render(finder_pending)['label'], 'Edits confirmed')


    def finder_only(self):
        repo = copy.deepcopy(self.good)
        repo['verification'].update(state='different', ignored_finder_only=True, backup_required=False)
        return repo

    def test_finder_display_success_preserves_raw_difference_and_exact_upload_requirement(self):
        repo = self.finder_only()
        original = copy.deepcopy(repo)
        rendered = self.render(repo)
        self.assertTrue(rendered['ready'])
        self.assertEqual(rendered['phase'], 'ready')
        self.assertEqual(rendered['label'], 'Backed up')
        self.assertEqual(rendered['headline'], 'Your files are backed up.')
        self.assertEqual(rendered['technicalDetail'],
                         'Only Finder view settings (.DS_Store) differ from the saved backup.')
        self.assertEqual(repo, original)
        self.report(repo)
        events = list(read_events(self.root/'logs'))
        presented = [e for e in events if e['event'] == 'ui_presented'][-1]
        self.assertEqual(presented['reason'], 'finder_only_project_match')
        facts = [e for e in events if e['event'] == 'status_repo'][-1]
        self.assertEqual(facts['verification_state'], 'different')
        self.assertTrue(facts['ignored_finder_only'])
        # The existing internal comparison remains a distinct background result.
        script = "const p=require('./web/repo-status.js');console.log(JSON.stringify(p.view(JSON.parse(require('fs').readFileSync(0,'utf8')))));"
        raw = json.loads(subprocess.check_output(['node', '-e', script], cwd=ROOT,
                                                input=json.dumps(repo), text=True))
        self.assertEqual(raw['phase'], 'background')
        self.assertFalse(raw['ready'])

    def test_finder_display_rejects_uncertain_stale_busy_and_meaningful_changes(self):
        base = self.finder_only()
        cases = []
        for state in ['pending', 'uploading', 'unknown', 'error']:
            row = copy.deepcopy(base)
            row['cloud']['state'] = state
            cases.append((row, {}))
        for field in ['sha256', 'archive']:
            row = copy.deepcopy(base)
            del row['last_backup'][field]
            cases.append((row, {}))
        for group, changes in [
            ('health', {'fresh': False}), ('cloud', {'archive': '/private/old'}),
            ('verification', {'archive': '/private/old'}),
            ('verification', {'backup_required': True}),
            ('verification', {'ignored_finder_only': False}),
            ('verification', {'state': 'checking'}),
            ('verification', {'state': 'changing'}),
        ]:
            row = copy.deepcopy(base)
            row[group].update(changes)
            cases.append((row, {}))
        row = copy.deepcopy(base)
        row['needs_backup'] = True
        row['verification'].update(ignored_finder_only=False, backup_required=True,
                                  changes={'counts': {'repo_files': 1, 'git_data': 0, 'finder_metadata': 1}})
        cases.append((row, {}))
        cases.append((base, {'running': True, 'current_repo_id': base['id']}))
        for row, backup in cases:
            with self.subTest(row=row, backup=backup):
                self.assertFalse(self.render(row, backup)['ready'])
                start = len(list(read_events(self.root/'logs')))
                payload = self.report(row, backup)
                self.assertFalse(any(e['event'] == 'presentation_input_disagreement'
                                     for e in list(read_events(self.root/'logs'))[start:]))
                # Diagnostics must reject a forged success for these same facts.
                payload['rows'][0].update(phase='ready', ready=True, category='backed_up',
                    display_label='Backed up', display_headline='Your files are backed up.')
                self.evidence.presentation(payload)
                self.assertTrue(any(e['event'] == 'presentation_input_disagreement'
                                    for e in list(read_events(self.root/'logs'))[start:]))

    def test_finder_diagnostics_keep_previous_display_versions_interpretable(self):
        repo = self.finder_only()
        payload = self.report(repo)
        facts = self.evidence.snapshots[payload['observation_id']][repo['id']]
        for version in ['status-clarity-1', 'status-clarity-2', 'status-clarity-3', 'status-clarity-4']:
            previous = copy.deepcopy(payload)
            previous['policy_version'] = version
            previous['rows'][0].update(phase='background', ready=False,
                                      **presentation_text(facts, 'background', version))
            previous['rows'][0].pop('card_timing')
            previous['rows'][0].pop('detail_timing')
            if version != 'status-clarity-4':
                previous.pop('selected_repo_id')
                previous['rows'][0].pop('timing')
            self.evidence.presentation(previous)
        self.assertFalse(any(e['event'] == 'presentation_input_disagreement'
                             for e in read_events(self.root/'logs')))
        payload['policy_version'] = 'status-clarity-4'
        payload['rows'][0].pop('card_timing')
        payload['rows'][0].pop('detail_timing')
        self.evidence.presentation(payload)
        self.assertTrue(any(e['event'] == 'presentation_input_disagreement'
                            for e in read_events(self.root/'logs')))

    def test_only_labels_require_complete_current_comparison(self):
        for finder, git, expected in [
            (1, 0, 'Only file metadata changed'),
            (0, 1, 'Only Git data changed'),
            (1, 1, 'Only Git and file metadata changed'),
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
                rendered = self.render(row)
                self.assertFalse(rendered['label'].startswith('Only '))
                if malformed.get('repo_files') != 1:
                    self.assertNotIn('still match', rendered['technicalDetail'])
                    self.assertNotIn('files match', rendered['technicalDetail'])
                    self.assertEqual(rendered['label'], 'Changes need verification')
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
        payload.pop('selected_repo_id')
        payload['rows'][0].pop('timing')
        payload['rows'][0].pop('card_timing')
        payload['rows'][0].pop('detail_timing')
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
            presented = [event for event in events if event['event'] == 'ui_presented'][-1]
            self.assertEqual(presented['reason'], 'presentation_inputs_disagree')

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
        actual = next(e for e in rows if e.get('policy_version') == 'status-clarity-7' and e['event'] == 'ui_presented')
        self.assertEqual(actual['category'], 'backed_up')
        self.assertEqual(actual['display_headline'], 'Your files are backed up.')
        for text in ['private-name', '/Users/private', '/private/current', 'private-repo', 'private-sha']:
            self.assertNotIn(text, shared)
        self.assertNotIn('category', rows[-1])
        self.assertNotIn('display_headline', rows[-1])
