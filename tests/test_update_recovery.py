import plistlib
from pathlib import Path
import tempfile
import unittest
from update_recovery import healthy, validate_record


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
