import base64
import copy
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.channel_policy import validate_channel_receipt
from tools.package_app import sha256
from tools.release_gate import REGISTER
from tools.update_feed import appcast
from tools.validate_signing import (
    require_manual_hosted_request, run, validation_plan, verify_result,
)

SHA = 'a' * 40
DIGEST = 'b' * 64


def gate():
    rules = json.loads(REGISTER.read_text())['rules']
    return {'result': 'passed', 'profile': 'macos', 'source_commit': SHA,
            'dirty_source': False, 'source_unchanged': True, 'source_digest': DIGEST,
            'python': {'successful': True, 'skipped': 0, 'tests_run': 1,
                       'outcomes': {name: 'passed' for rule in rules for name in rule['test_ids']}},
            'rules': [{'id': rule['id'], 'result': 'passed'} for rule in rules],
            'commands': [{'check': name, 'result': 'passed'} for name in (
                'native-app-build', 'coordinated-sparkle-package', 'github-workflow-syntax',
                'bridge-checks', 'updater-settings-checks')]}


class ValidateSigningTests(unittest.TestCase):
    def test_hosted_signing_requires_explicit_manual_request_and_exact_source(self):
        with tempfile.TemporaryDirectory() as folder:
            event = Path(folder) / 'event.json'
            event.write_text(json.dumps({'inputs': {'validate_signing': 'true'}}))
            environment = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'yogoldy/RepoHub',
                           'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_SHA': SHA,
                           'GITHUB_EVENT_PATH': str(event)}
            with patch.dict(os.environ, environment, clear=True):
                require_manual_hosted_request(SHA)
                for key, value in [('GITHUB_EVENT_NAME', 'push'),
                                   ('GITHUB_EVENT_NAME', 'pull_request'),
                                   ('GITHUB_REPOSITORY', 'foreign/RepoHub'),
                                   ('GITHUB_SHA', 'c' * 40)]:
                    with patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                        require_manual_hosted_request(SHA)
                for inputs in ({}, {'validate_signing': 'false'}):
                    event.write_text(json.dumps({'inputs': inputs}))
                    with self.assertRaises(ValueError):
                        require_manual_hosted_request(SHA)

    def test_failed_stale_skipped_or_changed_gate_never_opens_signing_material(self):
        changes = ({'source_commit': 'c' * 40}, {'result': 'failed'},
                   {'dirty_source': True}, {'source_unchanged': False},
                   {'python': {'successful': True, 'skipped': 1, 'tests_run': 1}},
                   {'source_digest': 'c' * 64})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for index, changeset in enumerate(changes):
                receipt = gate()
                receipt.update(copy.deepcopy(changeset))
                gate_path = root / f'gate-{index}.json'
                gate_path.write_text(json.dumps(receipt))
                output = root / f'result-{index}.json'
                with patch('tools.validate_signing.source_revision', return_value=SHA), \
                        patch('tools.validate_signing.source_fingerprint', return_value=DIGEST), \
                        patch('tools.validate_signing.require_manual_hosted_request'), \
                        patch('tools.validate_signing.signing_material') as material:
                    with self.assertRaises(ValueError):
                        run(gate_path, output)
                    material.assert_not_called()
                self.assertEqual(json.loads(output.read_text())['result'], 'failed')
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_validation_package_cannot_be_promoted_as_a_managed_release(self):
        plan = validation_plan(SHA)
        self.assertEqual(plan['version'], '0.0.0')
        self.assertEqual(plan['channel'], 'dev')
        with self.assertRaises(ValueError):
            validate_channel_receipt(dict(plan, distribution='developer_id', notarized=True,
                test_only=False, archive_sha256='c' * 64, archive_bytes=10))

    def fixture(self, folder):
        plan = validation_plan(SHA)
        archive = folder / plan['archive']
        archive.write_bytes(b'synthetic archive')
        receipt = dict(plan, test_only=False, distribution='developer_id', notarized=True,
                       archive_sha256=sha256(archive), archive_bytes=archive.stat().st_size)
        (folder / 'release-receipt.json').write_text(json.dumps(receipt))
        info = {'CFBundleIdentifier': 'com.leogoldberg.repohub',
                'SUPublicEDKey': base64.b64encode(b'x' * 32).decode(),
                'CFBundleName': 'Repo Hub', 'CFBundleVersion': plan['build'],
                'CFBundleShortVersionString': plan['version'], 'LSMinimumSystemVersion': '13.0'}
        (folder / 'appcast.xml').write_bytes(appcast(info, plan['archive_url'], 'synthetic',
            receipt['archive_bytes'], update_channel='dev'))
        return plan

    def test_artifact_corruption_or_extra_files_fail_before_signature_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = self.fixture(root)
            with patch('tools.validate_signing.command') as command:
                (root / plan['archive']).write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'archive_mismatch'):
                    verify_result(root, plan, root)
                command.assert_not_called()
                self.fixture(root)
                (root / 'unexpected.key').write_text('synthetic only')
                with self.assertRaisesRegex(ValueError, 'artifact_set'):
                    verify_result(root, plan, root)
                command.assert_not_called()

    def test_independent_signature_verifier_failure_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = self.fixture(root)
            with patch.dict(os.environ, {'REPOHUB_UPDATE_PUBLIC_KEY': 'configured-public-key'}), \
                    patch('tools.validate_signing.command', side_effect=[None, RuntimeError('invalid signature')]) as command:
                with self.assertRaises(RuntimeError):
                    verify_result(root, plan, root)
                self.assertEqual(command.call_args.args[0][-1], str(root / plan['archive']))
                self.assertEqual(command.call_args.args[0][1], 'configured-public-key')

    def exercise_run(self, root, *, changed=False, fail=False):
        gate_path = root / 'gate.json'
        gate_path.write_text(json.dumps(gate()))
        output = root / 'result.json'
        work_paths = []

        @contextmanager
        def material(work):
            work_paths.append(work)
            yield work / 'synthetic.p8', work / 'synthetic.key'

        def build(work, plan, mode, notary_key, update_key):
            self.assertEqual(mode, 'developer_id')
            if fail:
                raise RuntimeError('synthetic-password-must-not-escape')
            return work / 'artifacts'

        with patch('tools.validate_signing.source_revision', return_value=SHA), \
                patch('tools.validate_signing.source_fingerprint', side_effect=[DIGEST, 'c' * 64] if changed else [DIGEST, DIGEST]), \
                patch('tools.validate_signing.require_manual_hosted_request'), \
                patch('tools.validate_signing.signing_material', material), \
                patch('tools.validate_signing.build_artifacts', build), \
                patch('tools.validate_signing.verify_result', return_value={'archive_sha256': 'd' * 64, 'archive_bytes': 10}):
            if fail or changed:
                with self.assertRaises((ValueError, RuntimeError)):
                    run(gate_path, output)
            else:
                run(gate_path, output)
        self.assertTrue(work_paths)
        self.assertTrue(all(not path.exists() for path in work_paths))
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        return json.loads(output.read_text())

    def test_success_cleans_package_and_records_no_publication_or_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            report = self.exercise_run(Path(folder))
            self.assertEqual(report['result'], 'passed')
            self.assertTrue(report['source_unchanged'])
            self.assertFalse(report['published'])
            self.assertFalse(report['installed'])

    def test_failure_or_source_change_cleans_package_and_never_leaks_error_text(self):
        for options in ({'fail': True}, {'changed': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                report = self.exercise_run(Path(folder), **options)
                self.assertEqual(report['result'], 'failed')
                self.assertNotIn('synthetic-password', json.dumps(report))
                self.assertFalse(report['published'])

    def test_workflow_keeps_signing_opt_in_read_only_and_after_full_gate(self):
        text = (Path(__file__).resolve().parents[1] / '.github/workflows/golden-rules.yml').read_text()
        condition = "github.event_name == 'workflow_dispatch' && inputs.validate_signing && github.repository == 'yogoldy/RepoHub'"
        self.assertIn('default: false', text)
        self.assertIn('contents: read', text)
        self.assertNotIn('contents: write', text)
        self.assertNotIn('GH_TOKEN:', text)
        self.assertNotIn('REPOHUB_RELEASE_ENABLED:', text)
        self.assertNotIn('upload-artifact', text)
        self.assertIn('if: ' + condition, text)
        self.assertLess(text.index('tools/release_gate.py --require-clean'), text.index('tools/validate_signing.py'))
        self.assertLess(text.index('if: ' + condition), text.index('REPOHUB_CERTIFICATE_PASSWORD:'))
