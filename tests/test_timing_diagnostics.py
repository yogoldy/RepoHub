"""Selected secondary lines are checked without exporting exact dates."""
import copy
import json
from pathlib import Path
import tempfile
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
