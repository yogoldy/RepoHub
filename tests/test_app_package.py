import base64
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.package_app import extract, inventory, runtime_modules, validate_options, verify


class AppPackageTests(unittest.TestCase):
    def test_integrity_rejects_missing_changed_and_extra_components(self):
        with tempfile.TemporaryDirectory() as folder:
            resources = Path(folder)
            (resources / 'helper.py').write_text('original')
            manifest = {'schema': 1, 'files': inventory(resources)}
            (resources / 'release.json').write_text(json.dumps(manifest))
            self.assertEqual(verify(resources), manifest)
            (resources / 'helper.py').write_text('altered')
            with self.assertRaisesRegex(ValueError, 'component_mismatch'):
                verify(resources)
            (resources / 'helper.py').unlink()
            with self.assertRaisesRegex(ValueError, 'component_mismatch'):
                verify(resources)
            (resources / 'helper.py').write_text('original')
            (resources / 'foreign.py').write_text('unexpected')
            with self.assertRaisesRegex(ValueError, 'component_mismatch'):
                verify(resources)

    def test_links_cannot_escape_resources_and_link_changes_are_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            resources = Path(folder)
            (resources / 'python3').write_text('binary')
            (resources / 'python').symlink_to('python3')
            manifest = {'schema': 1, 'files': inventory(resources)}
            (resources / 'release.json').write_text(json.dumps(manifest))
            verify(resources)
            (resources / 'python').unlink()
            (resources / 'python').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'escaping_resource_link'):
                verify(resources)

    def test_production_requires_https_and_test_requires_disposable_identity(self):
        key = base64.b64encode(b'x' * 32).decode()
        validate_options('com.leogoldberg.repohub', 'https://example.com/feed.xml', key, False)
        validate_options('com.leogoldberg.repohub.test.upgrade', 'http://127.0.0.1:8781/feed.xml', key, True)
        for identifier, feed, test in [
            ('com.leogoldberg.repohub', 'http://127.0.0.1:8781/feed.xml', False),
            ('com.leogoldberg.repohub', 'http://127.0.0.1:8781/feed.xml', True),
            ('com.leogoldberg.repohub.test.upgrade', 'http://example.com/feed.xml', True),
            ('com.leogoldberg.repohub', 'https://user:secret@example.com/feed.xml', False),
        ]:
            with self.assertRaises(ValueError):
                validate_options(identifier, feed, key, test)
        with self.assertRaises(ValueError):
            validate_options('com.leogoldberg.repohub', 'https://example.com/feed.xml', 'bad', False)

    def test_dependency_archive_cannot_write_outside_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'malicious.tar'
            with tarfile.open(archive, 'w') as target:
                member = tarfile.TarInfo('../escaped')
                member.size = 4
                target.addfile(member, io.BytesIO(b'oops'))
            with self.assertRaises(tarfile.FilterError):
                extract(archive, root / 'unpacked')
            self.assertFalse((root / 'escaped').exists())

    def test_coordinated_bundle_uses_all_existing_runtime_dependencies(self):
        modules = runtime_modules()
        self.assertIn('repohub.py', modules)
        self.assertIn('diagnostic_export.py', modules)
        self.assertEqual(len(modules), len(set(modules)))
