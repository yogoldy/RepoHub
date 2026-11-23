import base64
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from tools.update_feed import appcast, validate_key_file, SPARKLE


class UpdateFeedTests(unittest.TestCase):
    def test_feed_uses_actual_build_signature_and_exact_length(self):
        info = {'CFBundleIdentifier': 'com.leogoldberg.repohub.test.feed',
                'RepoHubTestMode': True, 'SUPublicEDKey': base64.b64encode(b'x' * 32).decode(),
                'CFBundleName': 'RepoHub Test', 'CFBundleShortVersionString': '0.2.0',
                'CFBundleVersion': '103', 'LSMinimumSystemVersion': '13.0'}
        value = ET.fromstring(appcast(info, 'http://127.0.0.1:8781/update.zip', 'public-signature', 12345))
        self.assertEqual(value.find('channel/item/{' + SPARKLE + '}version').text, '103')
        enclosure = value.find('channel/item/enclosure')
        self.assertEqual(enclosure.attrib['length'], '12345')
        self.assertEqual(enclosure.attrib['{' + SPARKLE + '}edSignature'], 'public-signature')
        for url in ('file:///tmp/update.zip', 'http://outside.example/update.zip',
                    'https://example.com/update.zip?key=secret'):
            with self.assertRaises(ValueError):
                appcast(info, url, '', 0)
        info['RepoHubTestMode'] = False
        info['CFBundleIdentifier'] = 'com.leogoldberg.repohub'
        with self.assertRaises(ValueError):
            appcast(info, 'http://127.0.0.1:8781/update.zip', '', 0)

    def test_key_file_must_be_private_regular_and_owned(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test-only.key'
            path.write_text('disposable')
            path.chmod(0o600)
            validate_key_file(path)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                validate_key_file(path)
            path.chmod(0o600)
            alias = path.with_name('alias')
            alias.symlink_to(path)
            with self.assertRaises(ValueError):
                validate_key_file(alias)
