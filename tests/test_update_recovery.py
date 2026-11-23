import plistlib
from pathlib import Path
import tempfile
import unittest
from update_recovery import bundled_pythons, healthy, validate_record


class UpdateRecoveryTests(unittest.TestCase):
    def test_rollback_must_belong_to_this_identity_and_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / 'state'
            rollback = state / 'app-rollbacks/one/RepoHub Test.app'
            (rollback / 'Contents').mkdir(parents=True)
            info = {'CFBundleIdentifier': 'com.leogoldberg.repohub.test.recovery', 'CFBundleVersion': '100'}
            (rollback / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
            record = {'state': str(state), 'rollback': str(rollback),
                      'app': str(root / 'RepoHub Test.app'), 'bundle_id': info['CFBundleIdentifier'],
                      'target_build': '101', 'port': 8780}
            self.assertEqual(validate_record(record), (root / 'RepoHub Test.app', rollback, state))
            for patch in ({'bundle_id': 'different'}, {'rollback': str(root / 'foreign.app')},
                          {'port': True}, {'state': 'relative'}, {'target_build': '../other'}):
                with self.assertRaises(ValueError):
                    validate_record({**record, **patch})

    def test_old_or_unrelated_helper_cannot_confirm_replacement(self):
        record = {'target_build': '101', 'bundle_id': 'com.leogoldberg.repohub.test.recovery'}
        self.assertTrue(healthy({'application_release': {
            'build': '101', 'bundle_id': record['bundle_id']}}, record))
        for value in (None, {}, {'application_release': {'build': '100', 'bundle_id': record['bundle_id']}},
                      {'application_release': {'build': '101', 'bundle_id': 'foreign'}}):
            self.assertFalse(healthy(value, record))

    def test_bundled_interpreter_is_recognised_whatever_minor_version_it_pins(self):
        # The allowlist used to name python3.14 exactly, so bumping the bundled Python would make
        # the update guard refuse to stop the old helper ("shutdown_blocked").
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder) / 'RepoHub.app'
            bin_dir = app / 'Contents/Resources/python/bin'
            bin_dir.mkdir(parents=True)
            (bin_dir / 'python3.15').write_text('')
            (bin_dir / 'python3').symlink_to('python3.15')
            (bin_dir / 'python3-config').write_text('')
            (bin_dir / 'pip3').write_text('')
            found = bundled_pythons(app)
            self.assertIn(bin_dir / 'python3.15', found)
            self.assertIn(bin_dir / 'python3', found)
            self.assertNotIn(bin_dir / 'python3-config', found)
            self.assertNotIn(bin_dir / 'pip3', found)
            self.assertEqual(bundled_pythons(Path(folder) / 'missing.app'), set())
