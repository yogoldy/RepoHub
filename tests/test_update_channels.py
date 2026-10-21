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
            native = json.loads(next(line.split('=', 1)[1] for line in result.stdout.splitlines()
                                     if line.startswith('NATIVE_CHANNEL_EVIDENCE=')))
            self.assertEqual(native, {'update_channel': 'stable', 'experimental_channels': 'disabled'})
            release = {'source_revision': 'a' * 40, 'build': '10'}
            evidence = update_evidence(dict(release, update_phase='ready',
                                           update_reason='check_finished', **native), release)
            self.assertEqual(evidence['update_channel'], 'stable')
            self.assertEqual(evidence['experimental_channels'], 'disabled')
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

    def test_experimental_policy_diagnostics_reject_disagreement_and_export_bounded_values(self):
        release = {'source_revision': 'a' * 40, 'build': '10'}
        base = dict(release, update_phase='ready', update_reason='check_finished')
        rows = []
        for enabled, channel in [('disabled', 'stable'), ('enabled', 'stable'),
                                 ('enabled', 'dev'), ('enabled', 'testing')]:
            result = update_evidence(dict(base, experimental_channels=enabled, update_channel=channel), release)
            self.assertEqual(result, {'update_phase': 'ready', 'update_reason': 'check_finished',
                                     'update_channel': channel, 'experimental_channels': enabled})
            self.assertNotIn('backup_required', result)
            rows.append(result)
        for channel in ('dev', 'testing'):
            self.assertIsNone(update_evidence(dict(base, experimental_channels='disabled',
                                                  update_channel=channel), release))
        for value in (True, False, [], None, 'outside', '/private/token'):
            self.assertIsNone(update_evidence(dict(base, experimental_channels=value,
                                                  update_channel='stable'), release))
        self.assertIsNone(update_evidence(dict(base, experimental_channels='enabled'), release))
        self.assertIsNotNone(update_evidence(base, release))  # Older evidence remains readable.
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            log = DiagnosticLog(base / 'logs')
            for row in rows:
                log.emit('application_update', **row)
            log.emit('application_update', experimental_channels='/private/token')
            export_bundle(log.directory, base / 'export')
            exported = [json.loads(line) for path in (base / 'export').rglob('events.jsonl')
                        for line in path.read_text().splitlines()]
            self.assertEqual({row.get('experimental_channels') for row in exported}
                             - {None}, {'enabled', 'disabled'})
            self.assertNotIn('/private/token', json.dumps(exported))
