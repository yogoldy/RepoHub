"""Manual scans recheck synthetic sources without creating backups."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from repohub import Hub, Handler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


class RescanTests(unittest.TestCase):
    def test_menu_rescan_controller_requests_only_scanning_and_recovers_from_rejection(self):
        result = subprocess.run(['node', 'tests/rescan.cjs'], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_scan_api_guards_request_and_preserves_backup_when_files_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            repo = root / 'sources/Example'
            repo.mkdir(parents=True)
            (repo / 'work.txt').write_text('before')
            hub = Hub({'repos_root': str(repo.parent), 'backup_root': str(root/'backups'),
                       'state_dir': str(root/'state')})
            hub.backup()
            prior_index = copy.deepcopy(hub.index)
            prior_archives = {path: path.read_bytes() for path in (root/'backups').rglob('*.tar.gz')}
            (repo / 'work.txt').write_text('after')
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server.hub = hub
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            origin = f'http://127.0.0.1:{server.server_port}'
            headers = {'Origin': origin, 'Content-Type': 'application/json',
                       'X-RepoHub-Token': hub.csrf}
            finished = threading.Event()
            original_scan = hub.scan

            def observed_scan(**options):
                try:
                    return original_scan(**options)
                finally:
                    finished.set()

            try:
                for changes in ({'Origin': 'https://outside.example'},
                                {'Host': 'outside.example'}, {'X-RepoHub-Token': 'wrong'}):
                    request = urllib.request.Request(origin+'/api/scan', b'{}', {**headers, **changes})
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(request, timeout=5)
                    self.assertEqual(caught.exception.code, 403)
                    caught.exception.close()
                with patch.object(hub, 'scan', side_effect=observed_scan) as scan, \
                        patch.object(hub, 'backup') as backup:
                    request = urllib.request.Request(origin+'/api/scan', b'{}', headers)
                    with urllib.request.urlopen(request, timeout=5) as response:
                        self.assertEqual(response.status, 202)
                        self.assertTrue(json.load(response)['accepted'])
                    self.assertTrue(finished.wait(5))
                    scan.assert_called_once_with(force=True)
                    backup.assert_not_called()
                self.assertTrue(hub.status['repos'][0]['needs_backup'])
                self.assertEqual(hub.index, prior_index)
                self.assertEqual({path: path.read_bytes() for path in (root/'backups').rglob('*.tar.gz')},
                                 prior_archives)
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
