"""Selected secondary lines are checked without exporting exact dates."""
import copy
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from change_evidence import ChangeEvidence, presentation_text, timing_receipt
from diagnostics import DiagnosticLog, read_events
from diagnostic_export import export_bundle


class TimingDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = DiagnosticLog(self.root/'logs')
        self.evidence = ChangeEvidence(self.log)
        self.repo = {'id': 'private-id', 'name': 'private name', 'needs_backup': False,
                     'health': {'fresh': True}, 'last_backup': {'archive': '/private/archive', 'sha256': 'sha'},
                     'verification': {'state': 'matched', 'archive': '/private/archive'},
                     'cloud': {'state': 'uploaded', 'archive': '/private/archive'},
                     'schedule_evidence': {'state': 'scheduled', 'reason': 'periodic',
                         'due_at': '2026-10-16T19:00:00+00:00', 'due_in_seconds': 125},
                     'backup_location': {'state': 'cloud_confirmed', 'created_at': '2026-10-16T18:00:00+00:00'}}

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, freshness='current'):
        observation = self.evidence.observe_status({'repos': [self.repo], 'backup': {}})
        facts = self.evidence.snapshots[observation]['private-id']
        phase = 'ready' if freshness == 'current' else 'stale'
        text = presentation_text(facts, phase, 'status-clarity-4')
        return {'surface': 'menu', 'native': False, 'client_id': 'a'*24,
                'observation_id': observation, 'policy_version': 'status-clarity-4',
                'client_freshness': freshness, 'selected_repo_id': 'private-id',
                'rows': [{'repo_id': 'private-id', 'phase': phase, 'ready': phase == 'ready',
                          **text, 'timing': timing_receipt(facts, freshness)}]}

    def test_secondary_receipts_detect_wrong_date_location_and_countdown(self):
        payload = self.payload()
        self.evidence.presentation(payload)
        self.assertEqual(list(read_events(self.root/'logs'))[-1]['result'], 'complete')
        for changes in [{'due_at': '2026-10-16T20:00:00+00:00'}, {'location_state': 'local'},
                        {'created_at': '2026-10-15T18:00:00+00:00'}, {'remaining_minutes': 42},
                        {'inclusion_state': 'confirmed_changes'}]:
            changed = copy.deepcopy(payload)
            changed['rows'][0]['timing'].update(changes)
            self.evidence.presentation(changed)
            self.assertEqual(list(read_events(self.root/'logs'))[-1]['event'], 'timing_disagreement')
        self.evidence.presentation(self.payload('cache_expired'))
        self.assertEqual(list(read_events(self.root/'logs'))[-1]['result'], 'complete')

    def test_equivalent_polls_keep_evidence_identity_without_rewriting_snapshots(self):
        self.repo['schedule_evidence'].update(observed_at='2026-10-16T18:57:55+00:00')
        first = self.payload()
        original = copy.deepcopy(self.evidence.snapshots[first['observation_id']])
        self.repo['schedule_evidence'].update(observed_at='2026-10-16T18:58:00+00:00', due_in_seconds=122)
        second = self.payload()
        self.assertEqual(first['observation_id'], second['observation_id'])
        self.assertEqual(original, self.evidence.snapshots[first['observation_id']])
        self.repo['schedule_evidence']['due_in_seconds'] = 120
        self.assertNotEqual(first['observation_id'], self.payload()['observation_id'])

    def test_actual_javascript_timing_matches_original_receipts(self):
        root = Path(__file__).resolve().parents[1]
        cases = []
        for state in ['scheduled', 'due', 'busy', 'manual', 'unavailable', 'awaiting_edits', 'blocked']:
            row = copy.deepcopy(self.repo)
            row['schedule_evidence']['state'] = state
            cases.append((row, {}, 'current'))
        for state in ['cloud_confirmed', 'local', 'none', 'unavailable']:
            row = copy.deepcopy(self.repo)
            row['backup_location']['state'] = state
            cases.append((row, {}, 'current'))
        for counts in [{'repo_files': 1, 'git_data': 0, 'finder_metadata': 0},
                       {'repo_files': 0, 'git_data': 1, 'finder_metadata': 0},
                       {'repo_files': 0, 'git_data': 1, 'finder_metadata': 1},
                       {'repo_files': 0, 'git_data': 0, 'finder_metadata': 1}, {'git_data': 1}]:
            row = copy.deepcopy(self.repo)
            row['needs_backup'] = True
            row['verification'].update(state='different', changes={'counts': counts})
            cases.append((row, {}, 'current'))
            error = copy.deepcopy(row)
            error['cloud']['state'] = 'error'
            cases.append((error, {}, 'current'))
        cases.extend([(self.repo, {'running': True, 'current_repo_id': 'private-id'}, 'current'),
                      (self.repo, {}, 'cache_expired')])
        stale = copy.deepcopy(self.repo)
        stale['health']['fresh'] = False
        cases.append((stale, {}, 'current'))
        for repo, backup, freshness in cases:
            with self.subTest(state=repo['schedule_evidence']['state'], backup=backup, freshness=freshness):
                observation = self.evidence.observe_status({'repos': [repo], 'backup': backup})
                facts = self.evidence.snapshots[observation]['private-id']
                script = "const p=require('./web/repo-status.js');const i=JSON.parse(require('fs').readFileSync(0,'utf8'));console.log(JSON.stringify(p.timing(i.repo,i.backup,i.freshness)));"
                actual = json.loads(subprocess.check_output(['node', '-e', script], cwd=root, text=True,
                    input=json.dumps({'repo': repo, 'backup': backup, 'freshness': freshness})))
                self.assertEqual(actual['receipt'], timing_receipt(facts, freshness))
                if freshness != 'current':
                    self.assertNotIn('confirmed in iCloud', actual['lastLine'])
                    self.assertEqual(actual['nextLine'], 'Next check time unavailable.')
                if repo['backup_location']['state'] == 'cloud_confirmed' and freshness == 'current':
                    self.assertIn('Created', actual['lastLine'])
                    self.assertNotIn('uploaded at', actual['lastLine'])

    def test_compact_backup_facts_keep_location_and_creation_evidence(self):
        root = Path(__file__).resolve().parents[1]
        for state, freshness, expected in [
            ('cloud_confirmed', 'current', 'iCloud'),
            ('local', 'current', 'This Mac'),
            ('none', 'current', 'No backup yet'),
            ('unavailable', 'current', 'Unavailable'),
            ('cloud_confirmed', 'cache_expired', 'Unavailable'),
        ]:
            with self.subTest(state=state, freshness=freshness):
                repo = copy.deepcopy(self.repo)
                repo['backup_location']['state'] = state
                script = "const p=require('./web/repo-status.js');const r=JSON.parse(require('fs').readFileSync(0,'utf8'));console.log(JSON.stringify(p.timing(r.repo,{},r.freshness)));"
                actual = json.loads(subprocess.check_output(
                    ['node', '-e', script], cwd=root, text=True,
                    input=json.dumps({'repo': repo, 'freshness': freshness}),
                ))
                self.assertEqual(actual['locationLabel'], expected)
                if expected in ('iCloud', 'This Mac'):
                    self.assertRegex(actual['createdLabel'], r'^\d{1,2}/\d{1,2}/\d{2} \d{1,2}:\d{2}[ap]m$')
                    self.assertEqual(actual['receipt']['created_at'], repo['backup_location']['created_at'])
                elif expected == 'Unavailable':
                    self.assertEqual(actual['createdLabel'], 'Unavailable')
        # A claimed location without a usable creation observation stays unknown.
        repo['backup_location'] = {'state': 'cloud_confirmed', 'created_at': 'invalid'}
        actual = json.loads(subprocess.check_output(
            ['node', '-e', script], cwd=root, text=True,
            input=json.dumps({'repo': repo, 'freshness': 'current'}),
        ))
        self.assertEqual(actual['locationLabel'], 'Unavailable')
        self.assertEqual(actual['createdLabel'], 'Unavailable')

    def test_new_exports_are_bounded_and_exclude_private_calendar_evidence(self):
        self.evidence.presentation(self.payload())
        self.log.emit('ui_timing', schedule_state='/Users/private', remaining_minutes=10**50,
                      location_state='private name', inclusion_state='private prose')
        bundle = export_bundle(self.root/'logs', self.root/'export')
        shared = (bundle/'share/events.jsonl').read_text()
        self.assertNotIn('2026-10-16T', shared)
        for private in ['/private/archive', '/Users/private', 'private name', 'private prose', 'created_at', 'due_at']:
            self.assertNotIn(private, shared)
        rows = [json.loads(line) for line in shared.splitlines()]
        actual = next(row for row in rows if row['event'] == 'ui_timing' and row.get('result') == 'complete')
        self.assertEqual(actual['remaining_minutes'], 3)
        self.assertEqual(actual['location_state'], 'cloud_confirmed')
        self.assertNotIn('remaining_minutes', rows[-1])
        self.assertNotIn('schedule_state', rows[-1])

    def test_malformed_or_missing_selected_timing_receipts_fail_closed(self):
        payload = self.payload()
        for field, values in [('schedule_state', [[], {}, 'private prose']),
                              ('remaining_minutes', [True, -1, 1441, float('inf')]),
                              ('created_at', [[], '/Users/private', '2026-10-16'])]:
            for value in values:
                bad = copy.deepcopy(payload)
                bad['rows'][0]['timing'][field] = value
                with self.assertRaises(ValueError):
                    self.evidence.presentation(bad)
        del payload['rows'][0]['timing']
        with self.assertRaises(ValueError):
            self.evidence.presentation(payload)
