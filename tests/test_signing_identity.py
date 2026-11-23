from pathlib import Path
import plistlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.signing_identity import (
    COMPONENTS, TEAM_ID, check_metadata, designated_requirement, verify_identity,
)


def metadata(identifier):
    return (f'Identifier={identifier}\nTeamIdentifier={TEAM_ID}\n'
            'designated => ' + designated_requirement(identifier))


class SigningIdentityTests(unittest.TestCase):
    def test_changed_team_helper_identifier_or_hash_requirement_is_rejected(self):
        for _, _, identifier in COMPONENTS:
            valid = metadata(identifier)
            self.assertEqual(check_metadata(valid, identifier)['team'], TEAM_ID)
            self.assertEqual(check_metadata(valid.replace('"', ''), identifier),
                             check_metadata(valid, identifier))
            for invalid in (
                valid.replace(TEAM_ID, 'FOREIGN123'),
                valid.replace('Identifier=' + identifier, 'Identifier=another-helper'),
                valid.split('designated => ')[0] + 'designated => cdhash H"' + 'a' * 40 + '"',
                valid.replace('anchor apple generic', 'anchor trusted'),
                valid.replace('designated => ', '# designated => '),
                valid + ' and cdhash H"' + 'b' * 40 + '"',
            ):
                with self.subTest(identifier=identifier, invalid=invalid), \
                        self.assertRaisesRegex(ValueError, 'identity_changed'):
                    check_metadata(invalid, identifier)

    def test_package_inspection_checks_all_access_components_and_rejects_escaping_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder) / 'Repo Hub.app'
            app.mkdir()
            for _, relative, _ in COMPONENTS[1:]:
                path = app / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            responses = [SimpleNamespace(returncode=0, stdout='', stderr=metadata(identifier))
                         for _, _, identifier in COMPONENTS]
            with patch('tools.signing_identity.subprocess.run', side_effect=responses) as run:
                self.assertEqual(set(verify_identity(app)), {'app', 'helper', 'cloud'})
                self.assertTrue(all(call.args[0][:3] == ['/usr/bin/codesign', '-d', '-r-']
                                    for call in run.call_args_list))
            helper = app / COMPONENTS[1][1]
            helper.unlink()
            outside = Path(folder) / 'outside'
            outside.touch()
            helper.symlink_to(outside)
            with patch('tools.signing_identity.subprocess.run', return_value=responses[0]):
                with self.assertRaisesRegex(ValueError, 'outside_app'):
                    verify_identity(app)

    def test_packaging_and_archive_preparation_both_enforce_identity_before_delivery(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('package_app.py', 'update_feed.py'):
            source = (root / 'tools' / name).read_text()
            self.assertIn('verify_identity(app)', source)
        from tools.channel_policy import DEV_CHECKS
        self.assertIn('test_signing_identity.py', DEV_CHECKS)

    def test_wrong_identity_stops_archive_before_notarization_or_signing_key_use(self):
        from tools.update_feed import prepare
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / 'Repo Hub.app'
            (app / 'Contents').mkdir(parents=True)
            info = {'CFBundleIdentifier': 'com.leogoldberg.repohub', 'CFBundleVersion': '10'}
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
            key = root / 'synthetic.key'
            key.write_bytes(b'synthetic only')
            key.chmod(0o600)
            manifest = {'bundle_id': info['CFBundleIdentifier'], 'build': '10',
                        'distribution': 'developer_id'}
            with patch('tools.update_feed.verify', return_value=manifest), \
                    patch('tools.update_feed.subprocess.run') as run, \
                    patch('tools.update_feed.verify_identity', side_effect=ValueError('permission_signing_identity_changed')):
                with self.assertRaisesRegex(ValueError, 'identity_changed'):
                    prepare(app, root / 'output', 'https://example.com/update.zip', key, root / 'cache')
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], '/usr/bin/codesign')
            self.assertFalse((root / 'output').exists())
