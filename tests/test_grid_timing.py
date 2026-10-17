"""Every compact card and the optional expanded panel have separate observations."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from change_evidence import (ChangeEvidence, compact_timing_receipt, presentation_text,
                             timing_receipt)
from diagnostic_export import export_bundle
from diagnostics import DiagnosticLog, read_events


class GridTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.evidence = ChangeEvidence(DiagnosticLog(self.root/'logs'))
        self.repo = {'id': 'private-id', 'name': 'private name', 'needs_backup': False,
                     'health': {'fresh': True},
                     'last_backup': {'archive': '/private/archive', 'sha256': 'sha'},
                     'verification': {'state': 'matched', 'archive': '/private/archive'},
                     'cloud': {'state': 'uploaded', 'archive': '/private/archive'},
                     'schedule_evidence': {'state': 'scheduled', 'reason': 'periodic',
                         'due_at': '2026-10-17T23:00:00+00:00', 'due_in_seconds': 125},
                     'backup_location': {'state': 'cloud_confirmed',
                                         'created_at': '2026-10-17T18:00:00+00:00'}}

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, selected=None, freshness='current', repos=None):
        repos = repos or [self.repo, {**self.repo, 'id': 'other-id'}]
        observation = self.evidence.observe_status({'repos': repos, 'backup': {}})
        rows = []
        for repo in repos:
            facts = self.evidence.snapshots[observation][repo['id']]
            timing = timing_receipt(facts, freshness)
            phase = 'ready' if freshness == 'current' else 'stale'
            row = {'repo_id': repo['id'], 'phase': phase, 'ready': phase == 'ready',
                   **presentation_text(facts, phase, 'status-clarity-6'), 'timing': timing,
                   'card_timing': {**compact_timing_receipt(timing), 'text_matches': True}}
            if repo['id'] == selected:
                row['detail_timing'] = {'receipt': copy.deepcopy(timing), 'text_matches': True}
            rows.append(row)
        return {'surface': 'menu', 'native': False, 'client_id': 'a'*24,
                'observation_id': observation, 'policy_version': 'status-clarity-6',
                'client_freshness': freshness, 'selected_repo_id': selected, 'rows': rows}

    def events(self, event):
        return [row for row in read_events(self.root/'logs') if row['event'] == event]

    def test_all_cards_are_checked_with_no_expanded_selection(self):
        self.evidence.presentation(self.payload())
        timings = self.events('ui_timing')
        self.assertEqual(len(timings), 2)
        self.assertTrue(all(row['timing_surface'] == 'card' and row['result'] == 'complete'
                            for row in timings))
        payload = self.payload(freshness='cache_expired')
        self.evidence.presentation(payload)
        self.assertTrue(all(row['card_timing']['kind'] == 'unavailable' for row in payload['rows']))
        self.assertFalse(self.events('timing_disagreement'))

    def test_missing_wrong_or_hidden_card_time_is_detected_independently_of_detail(self):
        payload = self.payload(selected='private-id')
        self.evidence.presentation(payload)
        for target in (0, 1):
            for change in ({'text_matches': False}, {'due_at': None}, {'kind': 'backup'},
                           {'due_at': '2026-10-18T23:00:00+00:00'}):
                bad = copy.deepcopy(payload)
                bad['rows'][target]['card_timing'].update(change)
                self.evidence.presentation(bad)
                self.assertEqual(self.events('timing_disagreement')[-1]['timing_surface'], 'card')
                if target == 0:
                    self.assertEqual(self.events('ui_timing')[-1]['result'], 'complete')
                    self.assertEqual(self.events('ui_timing')[-1]['timing_surface'], 'detail')
                self.evidence.presentation(payload)
        bad = copy.deepcopy(payload)
        bad['rows'][0]['detail_timing']['text_matches'] = False
        self.evidence.presentation(bad)
        self.assertEqual(self.events('timing_disagreement')[-1]['timing_surface'], 'detail')

    def test_missing_receipts_and_inconsistent_expansion_fail_closed(self):
        for selected, target, field in [(None, 1, 'timing'), (None, 0, 'card_timing'),
                                        ('private-id', 0, 'detail_timing')]:
            payload = self.payload(selected)
            del payload['rows'][target][field]
            with self.assertRaises(ValueError):
                self.evidence.presentation(payload)
        payload = self.payload()
        payload['selected_repo_id'] = 'removed-id'
        with self.assertRaises(ValueError):
            self.evidence.presentation(payload)
        payload = self.payload('private-id')
        payload['selected_repo_id'] = None
        with self.assertRaises(ValueError):
            self.evidence.presentation(payload)

    def test_actual_compact_javascript_uses_same_timing_contract_for_every_state(self):
        root = Path(__file__).resolve().parents[1]
        cases = []
        for state in ['scheduled', 'due', 'busy', 'manual', 'awaiting_edits', 'blocked', 'unavailable']:
            for changed in (False, True):
                repo = copy.deepcopy(self.repo)
                repo['schedule_evidence']['state'] = state
                if changed:
                    repo['needs_backup'] = True
                    repo['verification'].update(state='different', changes={
                        'counts': {'repo_files': 1, 'git_data': 0, 'finder_metadata': 0}})
                for freshness in ('current', 'cache_expired'):
                    cases.append({'repo': repo, 'backup': {}, 'freshness': freshness})
        cases.append({'repo': self.repo, 'backup': {'running': True,
                       'current_repo_id': 'private-id'}, 'freshness': 'current'})
        script = """const p = require('./web/repo-status.js');
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
console.log(JSON.stringify(cases.map(i => {
  const timing = p.timing(i.repo, i.backup, i.freshness);
  return {timing, compact: p.compactTiming(timing)};
})));"""
        actual = json.loads(subprocess.check_output(['node', '-e', script], cwd=root,
                            input=json.dumps(cases), text=True))
        for case, rendered in zip(cases, actual):
            observation = self.evidence.observe_status({'repos': [case['repo']], 'backup': case['backup']})
            facts = self.evidence.snapshots[observation]['private-id']
            expected = timing_receipt(facts, case['freshness'])
            self.assertEqual(rendered['timing']['receipt'], expected)
            self.assertEqual({key: rendered['compact'][field] for key, field in
                              [('kind', 'kind'), ('due_at', 'dueAt')]}, compact_timing_receipt(expected))
            if expected['schedule_state'] == 'scheduled':
                self.assertIn('Next backup' if expected['inclusion_state'] != 'none'
                              else 'Next check', rendered['compact']['text'])
            self.assertNotIn('Next upload', rendered['compact']['text'])

    def test_grid_exports_identify_surfaces_without_calendar_or_private_text(self):
        self.evidence.presentation(self.payload('private-id'))
        payload = self.payload('private-id')
        payload['rows'][1]['card_timing']['text_matches'] = False
        self.evidence.presentation(payload)
        bundle = export_bundle(self.root/'logs', self.root/'export')
        text = (bundle/'share/events.jsonl').read_text()
        for private in ('private-id', 'private name', '/private/archive', '2026-10-17T',
                        'due_at', 'created_at'):
            self.assertNotIn(private, text)
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertTrue(any(row.get('policy_version') == 'status-clarity-6' for row in rows))
        self.assertEqual({row['timing_surface'] for row in rows if row['event'] == 'ui_timing'},
                         {'card', 'detail'})
