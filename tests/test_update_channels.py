import json
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest

from diagnostics import DiagnosticLog, read_events
from diagnostic_export import export_bundle
from tools.channel_policy import feed_url
from update_evidence import update_evidence

ROOT = Path(__file__).resolve().parents[1]


class UpdateChannelTests(unittest.TestCase):
    def test_shipped_channel_page_explicit_save_discard_and_conflicts(self):
        result = subprocess.run(['node', 'tests/update-channels.cjs'], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(platform.system() == 'Darwin', 'Native channel settings require macOS')
    def test_native_default_feed_isolation_and_revision_checked_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / 'channels'
            subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(Path(folder) / 'cache'),
                str(ROOT / 'native/AppUpdates.swift'), str(ROOT / 'native/PackagedApplication.swift'),
                str(ROOT / 'tests/update_channels.swift'), '-o', str(executable)], check=True,
                capture_output=True, text=True, timeout=120)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        source = (ROOT / 'native/AppUpdates.swift').read_text()
        for channel in ('dev', 'testing'):
            self.assertEqual(feed_url(channel), f'https://github.com/yogoldy/RepoHub/releases/download/repohub-channel-{channel}/appcast.xml')
        self.assertIn('resetUpdateCycleAfterShortDelay()', source)

    def test_channel_diagnostics_are_bounded_and_cannot_establish_backup_success(self):
        release = {'source_revision': 'a' * 40, 'build': '10'}
        native = dict(release, update_phase='ready', update_reason='channel_changed', update_channel='dev')
        result = update_evidence(native, release)
        self.assertEqual(result, {'update_phase': 'ready', 'update_reason': 'channel_changed', 'update_channel': 'dev'})
        for wrong in ('outside', '/private/secret', [], None):
            self.assertIsNone(update_evidence(dict(native, update_channel=wrong), release))
        self.assertIsNone(update_evidence(dict(native, build='11'), release))
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            log = DiagnosticLog(base / 'logs')
            log.emit('application_update', **result)
            log.emit('application_update', update_channel='/private/secret')
            self.assertTrue(any(row.get('update_channel') == 'dev' for row in read_events(log.directory)))
            export_bundle(log.directory, base / 'export')
            content = '\n'.join(path.read_text() for path in (base / 'export').rglob('*') if path.is_file())
            events = [json.loads(line) for path in (base / 'export').rglob('events.jsonl')
                      for line in path.read_text().splitlines()]
            self.assertTrue(any(row.get('update_channel') == 'dev' for row in events))
            self.assertNotIn('/private/secret', content)
