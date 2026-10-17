import json
from pathlib import Path
import tempfile
import unittest
from diagnostic_export import export_bundle
from diagnostics import DiagnosticLog
from update_evidence import update_evidence


class UpdateEvidenceTests(unittest.TestCase):
    def test_only_matching_release_and_bounded_facts_are_accepted(self):
        release = {'source_revision': 'a' * 40, 'build': '10'}
        value = {**release, 'update_phase': 'failed', 'update_reason': 'sparkle_aborted'}
        self.assertEqual(update_evidence(value, release), {
            'update_phase': 'failed', 'update_reason': 'sparkle_aborted'})
        for patch in ({'source_revision': 'b' * 40}, {'build': '11'},
                      {'update_phase': '/private/secret'}, {'update_reason': 'opaque exception'},
                      {'path': '/private/secret'}, {'update_phase': []}, {'update_reason': {}}):
            self.assertIsNone(update_evidence({**value, **patch}, release))
        self.assertIsNone(update_evidence(None, release))

    def test_update_facts_export_without_paths_or_raw_error_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            log = DiagnosticLog(root / 'logs')
            log.emit('application_update', update_phase='failed', update_reason='sparkle_aborted')
            log.emit('application_update', update_phase='/private/secret', update_reason='raw secret')
            output = export_bundle(root / 'logs', root / 'exports')
            self.assertNotIn('/private/secret', str(output))
            files = list((root / 'exports').rglob('*'))
            exported = '\n'.join(p.read_text() for p in files if p.is_file())
            self.assertIn('sparkle_aborted', exported)
            self.assertNotIn('/private/secret', exported)
            self.assertNotIn('raw secret', exported)
