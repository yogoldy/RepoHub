import base64
import contextlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import local_dev
from tools.channel_policy import DEV_CHECKS, feed_url

SHA = 'a' * 40
IDENTITY = 'Developer ID Application: Fixture (' + local_dev.TEAM_ID + ')'
ROOT = Path(__file__).resolve().parents[1]


def credentials():
    return {
        'REPOHUB_CERTIFICATE_P12': base64.b64encode(b'synthetic certificate').decode(),
        'REPOHUB_CERTIFICATE_PASSWORD': 'synthetic-password-never-log',
        'REPOHUB_SIGNING_IDENTITY': IDENTITY,
        'REPOHUB_NOTARY_KEY': 'synthetic-api-key-never-log',
        'REPOHUB_NOTARY_KEY_ID': 'ABC1234567',
        'REPOHUB_NOTARY_ISSUER': '11111111-2222-3333-4444-555555555555',
        'REPOHUB_SPARKLE_PRIVATE_KEY': base64.b64encode(b'x' * 32).decode(),
        'REPOHUB_UPDATE_PUBLIC_KEY': base64.b64encode(b'p' * 32).decode(),
    }


class LocalDevTests(unittest.TestCase):
    def test_publication_requires_local_host_clean_source_and_explicit_action(self):
        with patch('tools.local_dev.platform.system', return_value='Linux'):
            with self.assertRaisesRegex(local_dev.LocalDevError, 'local_macos'):
                local_dev.publish(True)
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}):
            with self.assertRaisesRegex(local_dev.LocalDevError, 'local_macos'):
                local_dev.publish(True)
        with patch('tools.local_dev.require_local'), patch('tools.local_dev.keychain') as secret:
            with self.assertRaisesRegex(local_dev.LocalDevError, 'explicit_dev'):
                local_dev.publish(False)
            with patch('tools.local_dev.subprocess.check_output', return_value=b'dirty'):
                with self.assertRaisesRegex(local_dev.LocalDevError, 'clean_source'):
                    local_dev.publish(True)
            secret.assert_not_called()

    def run_publication(self, home, fail='', changed=False):
        original = credentials()
        events = []
        held_environments = []
        def keychain(helper, action, payload=None):
            events.append(action)
            if action == 'status':
                return b'{"configured":true}'
            self.assertEqual(action, 'load')
            if fail == 'locked':
                raise local_dev.LocalDevError('keychain_cancelled_or_locked')
            return json.dumps(original).encode()

        def run(arguments, **kwargs):
            if 'tools/dev_gate.py' in arguments:
                events.append('gate')
                self.assertTrue(local_dev.CREDENTIAL_NAMES.isdisjoint(kwargs['env']))
                gate = Path(arguments[arguments.index('--output') + 1])
                gate.write_text(json.dumps({
                    'profile': 'dev', 'result': 'passed', 'source_commit': SHA,
                    'source_digest': 'c' * 64, 'dirty_source': False,
                    'source_unchanged': True, 'patterns': list(DEV_CHECKS),
                    'skipped': 0, 'tests_run': 123, 'native_build': True,
                }))
                return SimpleNamespace(returncode=1 if fail == 'gate' else 0)
            events.append('publish')
            self.assertEqual(arguments[1:4], ['tools/channel_release.py', 'dev', '--publish'])
            self.assertEqual(kwargs['env']['REPOHUB_RELEASE_MODE'], 'developer_id')
            self.assertEqual(kwargs['env']['REPOHUB_SPARKLE_PRIVATE_KEY'], original['REPOHUB_SPARKLE_PRIVATE_KEY'])
            held_environments.append(kwargs['env'])
            publication = {'published': 'repohub-v0.1.0-b10', 'channel': 'dev', 'feed_url': feed_url('dev')}
            return SimpleNamespace(returncode=1 if fail == 'publish' else 0,
                stdout=original['REPOHUB_CERTIFICATE_PASSWORD'] + '\n' + json.dumps(publication),
                stderr=original['REPOHUB_NOTARY_KEY'])

        def preflight(value):
            events.append('preflight')
            self.assertEqual(value, original)

        revision = [SHA, 'b' * 40] if changed else [SHA, SHA]
        with patch('tools.local_dev.HOME', home), patch('tools.local_dev.require_local'), \
                patch('tools.local_dev.clean_revision', side_effect=revision), \
                patch('tools.local_dev.configured_helper', return_value=home / 'trusted-helper'), \
                patch('tools.local_dev.keychain', side_effect=keychain), \
                patch('tools.local_dev.subprocess.run', side_effect=run), \
                patch('tools.local_dev.credential_preflight', side_effect=preflight), \
                patch('tools.local_dev.source_fingerprint', return_value='c' * 64), \
                patch('tools.local_dev.getpass.getpass', side_effect=AssertionError('Repeated secret prompt')):
            if fail or changed:
                with self.assertRaises(local_dev.LocalDevError):
                    local_dev.publish(True)
            else:
                self.assertEqual(local_dev.publish(True)['channel'], 'dev')
        for environment in held_environments:
            self.assertTrue(local_dev.CREDENTIAL_NAMES.isdisjoint(environment))
        if fail or changed:
            stages = {'gate': 'dev_gate', 'locked': 'credential_preflight', 'publish': 'publishing_dev'}
            failed = [json.loads(path.read_text()) for path in home.rglob('status.json')
                      if json.loads(path.read_text())['stage'] == 'failed']
            self.assertTrue(failed)
            self.assertEqual(failed[-1]['failed_stage'], 'dev_gate' if changed else stages[fail])
        for path in home.rglob('*'):
            if path.is_file():
                content = path.read_text()
                for name in ('REPOHUB_CERTIFICATE_PASSWORD', 'REPOHUB_NOTARY_KEY', 'REPOHUB_SPARKLE_PRIVATE_KEY'):
                    self.assertNotIn(original[name], content)
        return events

    def test_repeated_publications_use_keychain_after_gate_without_secret_prompts_or_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            for _ in range(2):
                self.assertEqual(self.run_publication(home), ['status', 'gate', 'load', 'preflight', 'publish'])
            self.assertEqual(len(list((home / 'runs').iterdir())), 2)

    def test_failed_gate_or_source_change_never_loads_credentials(self):
        for changed in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                events = self.run_publication(Path(temporary), '' if changed else 'gate', changed)
                self.assertEqual(events, ['status', 'gate'])

    def test_locked_keychain_and_failed_publish_stop_safely_and_allow_fresh_retry(self):
        for failure in ('locked', 'publish'):
            with tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                events = self.run_publication(home, failure)
                if failure == 'locked':
                    self.assertNotIn('publish', events)
                self.assertEqual(self.run_publication(home)[-1], 'publish')

    def test_untrusted_helper_invalid_credentials_and_unsafe_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            helper = Path(temporary) / 'fake-helper'
            helper.write_text('not a signed helper')
            helper.chmod(0o700)
            with patch('tools.local_dev.subprocess.run', return_value=SimpleNamespace(returncode=1)):
                with self.assertRaisesRegex(local_dev.LocalDevError, 'trusted_helper'):
                    local_dev.keychain(helper, 'load')
            unsafe = Path(temporary) / 'unsafe'
            unsafe.mkdir(mode=0o755)
            unsafe.chmod(0o755)
            with self.assertRaisesRegex(local_dev.LocalDevError, 'private_developer'):
                local_dev.private_directory(unsafe)
        for field, wrong in (('REPOHUB_SIGNING_IDENTITY', 'Apple Development: wrong'),
                             ('REPOHUB_SPARKLE_PRIVATE_KEY', 'typo'),
                             ('REPOHUB_NOTARY_KEY_ID', '../outside'),
                             ('REPOHUB_NOTARY_ISSUER', 'not-a-uuid')):
            with self.subTest(field=field), self.assertRaisesRegex(local_dev.LocalDevError, 'invalid_credentials'):
                local_dev.validate_credentials(dict(credentials(), **{field: wrong}))

    def test_setup_verifies_before_storing_and_never_overwrites_an_existing_item(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            certificate, notary = root / 'fixture.p12', root / 'fixture.p8'
            certificate.write_bytes(b'synthetic certificate')
            notary.write_text('synthetic-api-key-never-log')
            profile = root / 'profile.json'
            profile.write_text(json.dumps({
                'certificate_path': str(certificate), 'notary_key_path': str(notary),
                'signing_identity': IDENTITY, 'notary_key_id': 'ABC1234567',
                'notary_issuer': credentials()['REPOHUB_NOTARY_ISSUER'],
                'update_public_key': credentials()['REPOHUB_UPDATE_PUBLIC_KEY'],
            }))
            for path in (certificate, notary, profile):
                path.chmod(0o600)
            events = []
            def keychain(helper, operation, payload=None):
                events.append(operation)
                if operation == 'save':
                    self.assertEqual(json.loads(payload), credentials())
                return b'{"configured":false}'
            with patch('tools.local_dev.require_local'), \
                    patch('tools.local_dev.clean_revision', return_value=SHA), \
                    patch('tools.local_dev.prepare_helper', return_value=root / 'helper'), \
                    patch('tools.local_dev.sys.stdin.isatty', return_value=True), \
                    patch('tools.local_dev.credential_preflight', side_effect=lambda _:events.append('preflight')), \
                    patch('tools.local_dev.keychain', side_effect=keychain), \
                    patch('tools.local_dev.getpass.getpass', side_effect=[credentials()['REPOHUB_SPARKLE_PRIVATE_KEY'], credentials()['REPOHUB_CERTIFICATE_PASSWORD']]), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(local_dev.setup(profile)['published'])
                self.assertEqual(events, ['status', 'preflight', 'save'])
                self.assertNotIn(credentials()['REPOHUB_CERTIFICATE_PASSWORD'], output.getvalue())
            with patch('tools.local_dev.require_local'), \
                    patch('tools.local_dev.clean_revision', return_value=SHA), \
                    patch('tools.local_dev.prepare_helper', return_value=root / 'helper'), \
                    patch('tools.local_dev.sys.stdin.isatty', return_value=True), \
                    patch('tools.local_dev.keychain', return_value=b'{"configured":true}'), \
                    patch('tools.local_dev.getpass.getpass') as prompt:
                with self.assertRaisesRegex(local_dev.LocalDevError, 'already_configured'):
                    local_dev.setup(profile)
                prompt.assert_not_called()

    def test_cli_errors_never_echo_raw_exception_or_secret(self):
        previous_mask = os.umask(0o077)
        try:
            with patch('tools.local_dev.sys.argv', ['local_dev.py', 'publish', '--publish']), \
                    patch('tools.local_dev.publish', side_effect=RuntimeError('private-secret-text')), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(local_dev.main(), 1)
        finally:
            os.umask(previous_mask)
        self.assertNotIn('private-secret-text', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['reason'], 'local_dev_operation_failed')

    def test_wrong_update_public_key_never_imports_credentials_or_signs(self):
        with patch('tools.local_dev.subprocess.check_output', return_value='different-key'), \
                patch('tools.local_dev.subprocess.run') as run:
            with self.assertRaisesRegex(local_dev.LocalDevError, 'preflight_failed'):
                local_dev.credential_preflight(credentials())
            run.assert_not_called()

    @unittest.skipUnless(platform.system() == 'Darwin', 'macOS Keychain fixture requires macOS')
    def test_native_disposable_keychain_roundtrip_and_unsigned_helper_refusal(self):
        before = subprocess.check_output(['security', 'list-keychains', '-d', 'user'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / 'keychain-tests'
            sources = [ROOT / 'native/PublisherKeychain.swift', ROOT / 'tests/publisher_keychain.swift']
            subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(root / 'cache'),
                            *(str(path) for path in sources), '-o', str(executable)],
                           check=True, capture_output=True, timeout=120)
            result = subprocess.run([str(executable), str(root / 'fixture.keychain-db')],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('locked-item refusal passed', result.stdout)
            sources[-1] = ROOT / 'native/PublisherCredentials.swift'
            subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(root / 'cache'),
                            *(str(path) for path in sources), '-o', str(executable)],
                           check=True, capture_output=True, timeout=120)
            result = subprocess.run([str(executable), 'status'], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr.strip(), 'publisher_credentials_unavailable')
        self.assertEqual(before, subprocess.check_output(['security', 'list-keychains', '-d', 'user']))

    @unittest.skipUnless(platform.system() == 'Darwin', 'codesign predicate fixture requires macOS')
    def test_codesign_predicate_is_inline_and_checks_the_fixture_identifier(self):
        with tempfile.TemporaryDirectory() as temporary:
            helper = Path(temporary) / 'signed-fixture'
            shutil.copyfile('/usr/bin/true', helper)
            helper.chmod(0o700)
            subprocess.run(['codesign', '--force', '--sign', '-', '--identifier',
                            'repohub.publisher.fixture', str(helper)],
                           check=True, capture_output=True, timeout=20)
            with patch('tools.local_dev.helper_requirement', return_value='identifier "repohub.publisher.fixture"'):
                local_dev.verify_helper(helper)
            with patch('tools.local_dev.helper_requirement', return_value='identifier "foreign"'):
                with self.assertRaisesRegex(local_dev.LocalDevError, 'trusted_helper'):
                    local_dev.verify_helper(helper)

    def test_local_signing_tool_and_secrets_never_ship_to_app_users(self):
        from tools.package_app import NATIVE, runtime_modules
        self.assertNotIn('PublisherCredentials.swift', NATIVE)
        self.assertNotIn('PublisherKeychain.swift', NATIVE)
        self.assertNotIn('local_dev.py', runtime_modules())
        self.assertIn('test_local_dev.py', DEV_CHECKS)
