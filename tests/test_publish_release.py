import base64
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools.package_app import sha256
from tools.publish_release import publish_verified, require_gate, signing_material, verify_artifacts
from tools.release_policy import release_plan
from tools.update_feed import appcast

SHA = 'a' * 40


class FakeGitHub:
    def __init__(self, artifacts, fail=None):
        self.artifacts = artifacts
        self.fail = fail
        self.events = []
        self.checks = 0

    def event(self, name):
        self.events.append(name)
        if self.fail == name:
            raise RuntimeError('controlled_failure')

    def assert_source(self, run_id, revision):
        self.checks += 1
        self.event('source-' + str(self.checks))

    def create_draft(self, plan):
        self.event('draft')

    def upload(self, plan, artifacts):
        self.event('upload')

    def download(self, tag, directory):
        self.event('download')
        for path in self.artifacts.iterdir():
            shutil.copy2(path, directory / path.name)
        if self.fail == 'corrupt-download':
            (directory / 'appcast.xml').write_text('<invalid/>')

    def publish(self, plan):
        self.event('publish')

    def latest(self):
        self.event('latest')
        return {'tag_name': 'repohub-v0.0.6-b6' if self.fail != 'wrong-latest' else 'foreign'}

    def releases(self):
        return [{'tag_name': f'repohub-v0.0.{number}-b{number}', 'draft': False}
                for number in range(1, 7)] + [{'tag_name': 'unrelated'}]

    def receipt(self, release):
        self.event('verify-' + release['tag_name'])

    def remove_package(self, release):
        self.event('remove-' + release['tag_name'])


class PublishReleaseTests(unittest.TestCase):
    def fixture(self, root):
        plan = release_plan([{'tag_name': 'repohub-v0.0.5-b5'}], SHA)
        archive = root / plan['archive']
        archive.write_bytes(b'controlled archive bytes')
        receipt = dict(plan, test_only=False, archive_sha256=sha256(archive), archive_bytes=archive.stat().st_size)
        (root / 'release-receipt.json').write_text(json.dumps(receipt))
        info = {'CFBundleIdentifier': 'com.leogoldberg.repohub',
                'SUPublicEDKey': base64.b64encode(b'x' * 32).decode(), 'CFBundleName': 'Repo Hub',
                'CFBundleVersion': plan['build'], 'CFBundleShortVersionString': plan['version'],
                'LSMinimumSystemVersion': '13.0'}
        signature = base64.b64encode(b's' * 64).decode()
        (root / 'appcast.xml').write_bytes(appcast(info, plan['archive_url'], signature, receipt['archive_bytes']))
        return plan

    def test_publish_verifies_draft_then_latest_before_scoped_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            artifacts = Path(folder)
            plan = self.fixture(artifacts)
            github = FakeGitHub(artifacts)
            result = publish_verified(github, plan, artifacts, 123)
        self.assertEqual(result['published'], plan['tag'])
        self.assertEqual(github.events, [
            'source-1', 'draft', 'upload', 'download', 'source-2', 'publish', 'latest',
            'verify-repohub-v0.0.2-b2', 'verify-repohub-v0.0.1-b1',
            'remove-repohub-v0.0.2-b2', 'remove-repohub-v0.0.1-b1'])

    def test_upload_corruption_or_new_main_never_publishes_or_prunes(self):
        failures = ('upload', 'corrupt-download', 'source-2')
        for failure in failures:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                artifacts = Path(folder)
                plan = self.fixture(artifacts)
                github = FakeGitHub(artifacts, failure)
                with self.assertRaises((ValueError, RuntimeError)):
                    publish_verified(github, plan, artifacts, 123)
                self.assertNotIn('publish', github.events)
                self.assertFalse(any(item.startswith('remove-') for item in github.events))

    def test_unconfirmed_latest_or_foreign_historical_receipt_prevents_all_deletion(self):
        for failure in ('wrong-latest', 'verify-repohub-v0.0.1-b1'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                artifacts = Path(folder)
                plan = self.fixture(artifacts)
                github = FakeGitHub(artifacts, failure)
                with self.assertRaises((ValueError, RuntimeError)):
                    publish_verified(github, plan, artifacts, 123)
                self.assertFalse(any(item.startswith('remove-') for item in github.events))

    def test_missing_altered_or_test_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            artifacts = Path(folder)
            plan = self.fixture(artifacts)
            verify_artifacts(artifacts, plan)
            unexpected = artifacts / 'private-extra.key'
            unexpected.write_text('synthetic-only')
            with self.assertRaises(ValueError):
                verify_artifacts(artifacts, plan)
            unexpected.unlink()
            archive = artifacts / plan['archive']
            archive.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                verify_artifacts(artifacts, plan)
            plan = self.fixture(artifacts)
            receipt = json.loads((artifacts / 'release-receipt.json').read_text())
            receipt['test_only'] = True
            (artifacts / 'release-receipt.json').write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):
                verify_artifacts(artifacts, plan)
            self.fixture(artifacts)
            feed = artifacts / 'appcast.xml'
            feed.write_bytes(feed.read_bytes().replace(b'length="24"', b'length="999"'))
            with self.assertRaises(ValueError):
                verify_artifacts(artifacts, plan)

    def test_gate_must_be_clean_exact_macos_and_passed(self):
        receipt = {'result': 'passed', 'profile': 'macos', 'source_commit': SHA,
                   'dirty_source': False, 'source_unchanged': True}
        require_gate(receipt, SHA)
        for field, value in {'result': 'failed', 'profile': 'portable', 'source_commit': 'b' * 40,
                             'dirty_source': True, 'source_unchanged': False}.items():
            with self.assertRaises(ValueError):
                require_gate(dict(receipt, **{field: value}), SHA)

    def test_signing_requires_complete_secrets_and_always_restores_keychain_search(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError), signing_material(Path(folder)):
                self.fail('Missing signing credentials accepted')
        environment = {
            'REPOHUB_CERTIFICATE_P12': base64.b64encode(b'controlled certificate').decode(),
            'REPOHUB_CERTIFICATE_PASSWORD': 'synthetic-only',
            'REPOHUB_SIGNING_IDENTITY': 'Developer ID Application: synthetic-only',
            'REPOHUB_NOTARY_KEY': 'synthetic-only', 'REPOHUB_NOTARY_KEY_ID': 'synthetic-only',
            'REPOHUB_NOTARY_ISSUER': 'synthetic-only', 'REPOHUB_SPARKLE_PRIVATE_KEY': 'synthetic-only',
        }
        calls = []
        def command(arguments):
            calls.append(arguments)
            if arguments == ['security', 'list-keychains', '-d', 'user']:
                return '"/synthetic/login.keychain-db"'
            if arguments[1] == 'create-keychain':
                Path(arguments[-1]).touch()
            return ''
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, environment, clear=True):
            work = Path(folder)
            with patch('tools.publish_release.command', side_effect=command):
                with self.assertRaisesRegex(RuntimeError, 'controlled'), signing_material(work) as files:
                    self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in files))
                    raise RuntimeError('controlled')
            self.assertFalse((work / 'signing.p12').exists())
            self.assertFalse((work / 'notary.p8').exists())
            self.assertFalse((work / 'sparkle.key').exists())
        self.assertIn(['security', 'list-keychains', '-d', 'user', '-s', '/synthetic/login.keychain-db'], calls)
        self.assertEqual(calls[-1][1], 'delete-keychain')
