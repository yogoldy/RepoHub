"""Actual menu rendering and compact/detail observations use isolated DOM doubles."""
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from change_evidence import ChangeEvidence
from diagnostics import DiagnosticLog, read_events


class MenuCardTests(unittest.TestCase):
    def test_actual_card_controller_and_timing_dom_faults(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', str(root/'tests/menu-cards.cjs')], cwd=root,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_controller_observations_reach_independent_diagnostic_checks(self):
        root = Path(__file__).resolve().parents[1]
        output = subprocess.check_output(['node', str(root/'tests/menu-cards.cjs'), '--proofs'],
                                         cwd=root, text=True, timeout=15)
        proofs = json.loads(output.splitlines()[-1])
        with tempfile.TemporaryDirectory() as temp:
            log = DiagnosticLog(Path(temp)/'logs')
            evidence = ChangeEvidence(log)
            for index, proof in enumerate(proofs):
                with self.subTest(case=proof['label']):
                    observation = evidence.observe_status(proof['status'])
                    before = len(list(read_events(log.directory)))
                    evidence.presentation({'surface': 'menu', 'native': False,
                        'client_id': f'{index:024x}', 'observation_id': observation,
                        'policy_version': 'status-clarity-6', 'client_freshness': 'current',
                        'selected_repo_id': proof['selected'], 'rows': proof['rows']})
                    events = list(read_events(log.directory))[before:]
                    failures = [row for row in events if row['event'] == 'timing_disagreement']
                    self.assertFalse([row for row in events
                                      if row['event'] == 'presentation_input_disagreement'])
                    if proof['failedSurface']:
                        self.assertEqual(len(failures), 1)
                        self.assertEqual(failures[0]['timing_surface'], proof['failedSurface'])
                    else:
                        self.assertFalse(failures)
            self.assertEqual(log.failed, 0)
