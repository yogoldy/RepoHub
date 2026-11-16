"""One RepoHub helper owns the local port; another copy reports itself and never outlives its app."""
import json
import plistlib
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from diagnostics import read_events
from repohub import Hub, ThreadingHTTPServer, watch_parent
from update_evidence import REASONS
from update_recovery import guard

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = 'com.leogoldberg.repohub.test.conflict'
CHILD = """
import sys
from pathlib import Path
import repohub
root = Path(sys.argv[1])
original = repohub.load_json
release = {'source_revision': 'a' * 40, 'build': '13', 'bundle_id': 'com.leogoldberg.repohub.test.conflict'}
repohub.load_json = lambda path, default: release if Path(path).name == 'release.json' else original(path, default)
repohub.Hub.automatic_tick = lambda self: None
repohub.Hub.refresh_cloud = lambda self: None
sys.argv = ['repohub.py', '--config', str(root / 'config.json'), '--bundled']
repohub.main()
"""
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class OtherCopy(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'application_release': {'build': '12', 'bundle_id': BUNDLE, 'source_revision': 'b' * 40},
                           'repos': []}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class HelperConflictTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        repo = self.base / 'repos/Example'
        repo.mkdir(parents=True)
        (repo / 'work.txt').write_text('work')
        (self.base / 'cloud').mkdir()
        self.config = {'repos_root': str(repo.parent), 'backup_root': str(self.base / 'cloud/Backups'),
                       'state_dir': str(self.base / 'state'), 'retention': 'latest',
                       'cloud_helper': '/nonexistent-test-provider', 'scan_seconds': 3600}

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, port):
        (self.base / 'config.json').write_text(json.dumps({**self.config, 'port': port}))

    def conflict(self):
        return json.loads((self.base / 'state/helper-conflict.json').read_text())

    def logs(self):
        return ''.join(json.dumps(event) for event in read_events(self.base / 'state/diagnostics'))

    def run_child(self, port):
        self.write_config(port)
        return subprocess.run([sys.executable, '-B', '-c', CHILD, str(self.base)], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)

    def test_second_helper_reports_another_copy_and_leaves_it_running(self):
        other = ThreadingHTTPServer(('127.0.0.1', 0), OtherCopy)
        threading.Thread(target=other.serve_forever, daemon=True).start()
        try:
            result = self.run_child(other.server_port)
            self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            conflict = self.conflict()
            self.assertEqual((conflict['reason'], conflict['own_build'], conflict['other_build']),
                             ('another_copy_running', '13', '12'))
            with OPENER.open('http://127.0.0.1:%d/api/status' % other.server_port, timeout=2) as response:
                self.assertEqual(json.load(response)['application_release']['build'], '12',
                                 'The other copy keeps running untouched')
        finally:
            other.shutdown()
            other.server_close()
        logs = self.logs()
        self.assertIn('helper_conflict', logs)
        self.assertIn('another_copy_running', logs)
        self.assertNotIn(str(self.base), logs)
        # A listener that is not RepoHub is a plain port conflict, never another copy.
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            sock.listen()
            result = self.run_child(sock.getsockname()[1])
        self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
        self.assertEqual(self.conflict()['reason'], 'port_in_use')

    def test_successful_start_clears_a_stale_conflict(self):
        port = free_port()
        self.write_config(port)
        (self.base / 'state').mkdir()
        stale = self.base / 'state/helper-conflict.json'
        stale.write_text(json.dumps({'reason': 'another_copy_running', 'own_build': '13'}))
        log = (self.base / 'child.log').open('w')
        process = subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(self.base)], cwd=ROOT, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 15
            while True:
                try:
                    with OPENER.open('http://127.0.0.1:%d/api/session' % port, timeout=1):
                        break
                except OSError:
                    if time.monotonic() > deadline or process.poll() is not None:
                        log.flush()
                        self.fail('Helper did not start:\n' + (self.base / 'child.log').read_text()[-3000:])
                    time.sleep(.05)
            self.assertFalse(stale.exists())
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=10), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            log.close()

    def test_helper_stops_after_its_app_exits_but_never_mid_backup(self):
        hub = Hub({**self.config, 'port': free_port()})
        parents = iter([500, 500])
        stopped = threading.Event()
        hub.backup_lock.acquire()
        threading.Thread(target=watch_parent, args=(hub, 500),
                         kwargs={'getppid': lambda: next(parents, 1), 'interval': 0.01, 'stop': stopped.set},
                         daemon=True).start()
        time.sleep(0.3)
        self.assertFalse(stopped.is_set(), 'An active backup finishes before the helper stops')
        hub.backup_lock.release()
        self.assertTrue(stopped.wait(5))
        self.assertIn('helper_parent_exited', self.logs())

    def test_update_watchdog_reports_another_copy_instead_of_rolling_back(self):
        state = self.base / 'watch-state'
        rollback = state / 'app-rollbacks/one/RepoHub Test.app'
        (rollback / 'Contents').mkdir(parents=True)
        app = self.base / 'RepoHub Test.app'
        (app / 'Contents').mkdir(parents=True)
        (rollback / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': BUNDLE, 'CFBundleVersion': '12'}))
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': BUNDLE, 'CFBundleVersion': '13'}))
        record = {'app': str(app), 'rollback': str(rollback), 'state': str(state), 'bundle_id': BUNDLE,
                  'target_build': '13', 'port': free_port()}
        conflict = state / 'helper-conflict.json'
        conflict.write_text(json.dumps({'reason': 'another_copy_running', 'own_build': '13', 'other_build': '12'}))
        self.assertEqual(guard(record, timeout=0.2), 'another_copy_running')
        self.assertEqual(plistlib.loads((app / 'Contents/Info.plist').read_bytes())['CFBundleVersion'], '13',
                         'The correctly installed build stays in place')
        # Only this build's own conflict counts; anything else follows the normal recovery path.
        for value in ({'reason': 'another_copy_running', 'own_build': '12'}, {'reason': 'port_in_use', 'own_build': '13'}):
            conflict.write_text(json.dumps(value))
            self.assertEqual(guard(record, timeout=0.2), 'process_evidence_missing')
        self.assertIn('another_copy_running', REASONS)


if __name__ == '__main__':
    unittest.main()
