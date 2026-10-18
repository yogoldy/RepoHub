import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from diagnostic_export import export_bundle
from repohub import Hub, Handler, ThreadingHTTPServer


class SetupAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.cloud = self.root / 'cloud'; self.cloud.mkdir()
        self.dest = self.cloud / 'Backups'; self.dest.mkdir()
        self.source = self.root / 'sources/Ordinary'; self.source.mkdir(parents=True)
        (self.source / 'work').write_text('non-Git contents')
        self.hub = Hub({'sources': {'mode': 'manual', 'paths': []}, 'setup_required': True,
                        'state_dir': str(self.root / 'state'), 'backup_root': str(self.dest),
                        '_setup_test_cloud_root': str(self.cloud)})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); self.server.hub = self.hub
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True); self.worker.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.headers = {'Origin': self.origin, 'X-RepoHub-Token': self.hub.csrf, 'Content-Type': 'application/json'}

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.worker.join(); self.temp.cleanup()

    def request(self, path, value=None, headers=None):
        request = urllib.request.Request(self.origin + path, json.dumps(value).encode() if value is not None else None,
                                         headers or self.headers)
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)

    def finish_operation(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            _, result = self.request('/api/setup/operation')
            if result['state'] in {'complete', 'failed'}:
                return result
            time.sleep(.005)
        self.fail('Setup operation did not finish')

    def test_setup_and_discovery_require_host_origin_token_and_review_before_save(self):
        for path in ['/api/setup/review', '/api/setup/apply', '/api/setup/continue',
                     '/api/discovery/start', '/api/discovery/cancel']:
            for changes in [{'Origin': 'https://outside.example'}, {'X-RepoHub-Token': 'wrong'}, {'Host': 'outside.example'}]:
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.request(path, {}, {**self.headers, **changes})
                self.assertEqual(caught.exception.code, 403); caught.exception.close()
        self.request('/api/setup/apply', {'draft': {}, 'review': 'forged', 'backup_now': False})
        self.assertEqual(self.finish_operation()['state'], 'failed')
        self.assertFalse(self.hub.configured)
        self.assertFalse((self.hub.data_dir / 'setup.json').exists())

    def test_full_http_review_apply_and_restart_preserve_non_git_source(self):
        _, status = self.request('/api/setup')
        draft = {key: status[key] for key in ['source', 'destination', 'settings', 'revision', 'discovery_parent']}
        draft['source']['paths'] = [str(self.source)]; draft['destination'] = str(self.dest)
        code, _ = self.request('/api/setup/review', draft); self.assertEqual(code, 202)
        operation = self.finish_operation(); self.assertEqual(operation['state'], 'complete')
        review = operation['value']
        self.assertEqual(review['workspaces'][0]['backup_path'], str(self.dest / 'Ordinary'))
        self.assertFalse(self.hub.configured, 'Review cannot enable fresh-install backups')
        self.request('/api/setup/apply', {'draft': draft, 'review': review['review'], 'backup_now': False})
        self.assertEqual(self.finish_operation()['state'], 'complete')
        self.assertTrue(self.hub.configured)
        self.assertFalse(self.hub.index)
        self.assertEqual(list(self.hub.repositories().values()), [self.source])
        self.hub.backup()
        self.assertTrue(list((self.dest / 'Ordinary').glob('*.tar.gz')))

    def test_setup_resources_are_served_from_explicit_routes(self):
        for path in ['/setup.html', '/setup.js', '/setup.css']:
            with urllib.request.urlopen(self.origin + path, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.origin + '/setup/../../config.json', timeout=5)
        self.assertEqual(caught.exception.code, 404); caught.exception.close()

    def test_setup_diagnostics_export_only_typed_results_without_selected_paths(self):
        _, status = self.request('/api/setup')
        draft = {key: status[key] for key in ['source', 'destination', 'settings', 'revision', 'discovery_parent']}
        draft['source']['paths'] = [str(self.source)]; draft['destination'] = str(self.dest)
        self.request('/api/setup/review', draft)
        review = self.finish_operation()['value']
        self.request('/api/setup/apply', {'draft': draft, 'review': review['review'], 'backup_now': False})
        self.assertEqual(self.finish_operation()['state'], 'complete')
        bundle = export_bundle(self.hub.diagnostics.directory, self.root / 'export')
        shared = (bundle / 'share/events.jsonl').read_text()
        self.assertIn('setup_review', shared); self.assertIn('setup_applied', shared)
        self.assertNotIn(str(self.root), shared); self.assertNotIn('Ordinary', shared)
        self.assertNotIn(review['review'], shared)
