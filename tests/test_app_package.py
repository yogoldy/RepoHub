import base64
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools.package_app import build, extract, inventory, runtime_modules, validate_options, verify


EXPECTED_WEB_ASSETS = {
    'app.js', 'diagnostics-client.js', 'index.html', 'menu-appearance.js',
    'menu.css', 'menu.html', 'menu.js', 'notes.html', 'readiness.css',
    'readiness.js', 'repo-status.js', 'report-preview.js', 'report.css',
    'style.css', 'view-client.js', 'workspace-setup.css', 'workspace-setup.js',
}


class AppPackageTests(unittest.TestCase):
    def package_source(self, root):
        web = root / 'web'
        web.mkdir()
        for name in EXPECTED_WEB_ASSETS:
            (web / name).write_text('asset:' + name)
        (root / 'install.py').write_text("for name in ('repohub.py',): pass\n")
        (root / 'repohub.py').write_text('# synthetic helper\n')
        return web

    def build_fixture(self, root):
        def unpack_dependency(archive, destination):
            if destination.name == 'sparkle':
                (destination / 'Sparkle.framework').mkdir(parents=True)
                (destination / 'LICENSE').write_text('synthetic license')
            else:
                (destination / 'python/python').mkdir(parents=True)
                (destination / 'python/python/python3').write_text('synthetic interpreter')

        # Only external compilation/signing and dependency downloads are stubbed.
        # The production build still selects, copies and inventories its resources.
        output = root / 'Built.app'
        with patch('tools.package_app.ROOT', root), \
                patch('tools.package_app.platform.system', return_value='Darwin'), \
                patch('tools.package_app.platform.machine', return_value='arm64'), \
                patch('tools.package_app.dependency', return_value=root / 'dependency.tar'), \
                patch('tools.package_app.extract', side_effect=unpack_dependency), \
                patch('tools.package_app.subprocess.check_output', side_effect=['fixture-source', b'']), \
                patch('tools.package_app.run'):
            build(output, root / 'cache', '0.1.0', '1',
                  'com.leogoldberg.repohub.test.assets', 'http://127.0.0.1:8781/appcast.xml',
                  base64.b64encode(b'x' * 32).decode(), test=True)
        return output

    def test_bundle_web_allowlist_excludes_unlisted_files_and_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            web = self.package_source(root)
            for name in ('.DS_Store', '.env', 'developer-notes.md', 'unlisted.js'):
                (web / name).write_text('not a shipped asset')
            (web / 'scratch').mkdir()
            (web / 'scratch/private.json').write_text('not a shipped asset')
            (web / 'private-link.html').symlink_to(root / 'repohub.py')

            app = self.build_fixture(root)
            resources = app / 'Contents/Resources'
            shipped = resources / 'runtime/web'
            self.assertEqual({path.name for path in shipped.iterdir()}, EXPECTED_WEB_ASSETS)
            for name in EXPECTED_WEB_ASSETS:
                self.assertEqual((shipped / name).read_text(), 'asset:' + name)
            manifest = verify(resources)
            web_entries = {name.removeprefix('runtime/web/') for name in manifest['files']
                           if name.startswith('runtime/web/')}
            self.assertEqual(web_entries, EXPECTED_WEB_ASSETS)
            self.assertTrue((web / 'scratch/private.json').exists())

    def test_bundle_web_allowlist_rejects_missing_or_linked_required_assets(self):
        for invalid in ('missing', 'linked-file', 'linked-directory'):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                web = self.package_source(root)
                if invalid == 'linked-directory':
                    web.rename(root / 'real-web')
                    web.symlink_to(root / 'real-web', target_is_directory=True)
                else:
                    (web / 'menu.html').unlink()
                    if invalid == 'linked-file':
                        (web / 'menu.html').symlink_to(root / 'repohub.py')
                with self.assertRaisesRegex(ValueError, 'invalid_web_asset'):
                    self.build_fixture(root)
                self.assertFalse((root / 'Built.app').exists())

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
