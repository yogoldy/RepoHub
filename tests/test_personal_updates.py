import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.package_app import distribution_mode, update_defaults, validate_options
from tools.publish_release import build_artifacts, personal_signing_material, selected_mode
from tools.release_policy import release_plan, validate_receipt
from tools.update_feed import archive_distribution
from update_evidence import update_evidence


class PersonalUpdateTests(unittest.TestCase):
    def test_personal_mode_is_explicit_and_does_not_relax_identity_or_https(self):
        with self.assertRaises(ValueError):
            distribution_mode(False, False, None)
        self.assertEqual(distribution_mode(False, True, None), 'personal_adhoc')
        with self.assertRaises(ValueError):
            distribution_mode(True, True, None)
        with self.assertRaises(ValueError):
            distribution_mode(False, True, 'Developer ID Application: other')
        key = base64.b64encode(b'x' * 32).decode()
        for identifier, url in [('com.foreign.app', 'https://example.com/feed.xml'),
                                ('com.leogoldberg.repohub', 'http://example.com/feed.xml')]:
            with self.assertRaises(ValueError):
                validate_options(identifier, url, key, False)
        with patch.dict(os.environ, {'REPOHUB_RELEASE_MODE': 'skip-verification'}):
            with self.assertRaises(ValueError):
                selected_mode()

    def test_personal_archive_requires_matching_manifest_and_app_flags(self):
        info = {'CFBundleIdentifier': 'com.leogoldberg.repohub', 'RepoHubPersonalUpdates': True}
        manifest = {'distribution': 'personal_adhoc'}
        self.assertEqual(archive_distribution(info, manifest), 'personal_adhoc')
        for changed_info, changed_manifest in [
                (dict(info, RepoHubTestMode=True), manifest),
                (dict(info, CFBundleIdentifier='foreign'), manifest),
                (info, {'distribution': 'developer_id'}),
                ({}, manifest)]:
            with self.assertRaises(ValueError):
                archive_distribution(changed_info, changed_manifest)
        self.assertEqual(archive_distribution({}, {'distribution': 'developer_id'}), 'developer_id')

    def test_automatic_discovery_does_not_enable_silent_install_or_test_network_requests(self):
        settings = update_defaults(False)
        self.assertTrue(settings['SUEnableAutomaticChecks'])
        self.assertEqual(settings['SUScheduledCheckInterval'], 3600)
        self.assertFalse(settings['SUAutomaticallyUpdate'])
        self.assertFalse(settings['SUEnableSystemProfiling'])
        self.assertFalse(update_defaults(True)['SUEnableAutomaticChecks'])

    def test_personal_release_uses_sparkle_key_without_apple_credentials_and_cleans_it(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            with patch.dict(os.environ, {'REPOHUB_SPARKLE_PRIVATE_KEY': 'synthetic-only'}, clear=True):
                with self.assertRaisesRegex(RuntimeError, 'controlled'), personal_signing_material(work) as (notary, key):
                    self.assertIsNone(notary)
                    self.assertEqual(key.stat().st_mode & 0o777, 0o600)
                    raise RuntimeError('controlled')
            self.assertFalse((work / 'sparkle.key').exists())
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError), personal_signing_material(work):
                    self.fail('Missing archive signing key was accepted')

    def test_personal_path_keeps_archive_signing_but_never_calls_notarytool(self):
        plan = release_plan([], 'a' * 40)
        def prepare(app, output, archive_url, key, cache):
            output.mkdir()
            return {'source_revision': plan['source_revision'], 'build': plan['build'],
                    'test_only': False, 'distribution': 'personal_adhoc', 'notarized': False}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'REPOHUB_UPDATE_PUBLIC_KEY': 'public-only'}, clear=True):
            work = Path(folder)
            with patch('tools.publish_release.build') as builder:
                with patch('tools.publish_release.prepare', side_effect=prepare) as signer:
                    with patch('tools.publish_release.command') as command:
                        output = build_artifacts(work, plan, 'personal_adhoc', None, work / 'protected.key')
                        command.assert_not_called()
                    self.assertTrue(builder.call_args.kwargs['personal'])
                    self.assertIsNone(builder.call_args.kwargs['signing_identity'])
                    signer.assert_called_once()
            receipt = json.loads((output / 'release-receipt.json').read_text())
            self.assertFalse(receipt['notarized'])
            receipt.update(archive_sha256='b' * 64, archive_bytes=10)
            validate_receipt({'tag_name': plan['tag']}, receipt)

    def test_scheduled_checks_have_typed_private_diagnostic_evidence(self):
        release = {'source_revision': 'a' * 40, 'build': '1'}
        value = dict(release, update_phase='checking', update_reason='scheduled_check')
        expected = {'update_phase': 'checking', 'update_reason': 'scheduled_check'}
        self.assertEqual(update_evidence(value, release), expected)
        value['secret'] = 'synthetic-only'
        self.assertIsNone(update_evidence(value, release))
