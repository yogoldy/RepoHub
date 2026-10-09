import hashlib
import json
import os
from pathlib import Path
import tarfile
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repohub import Hub, Handler, ThreadingHTTPServer, snapshot, sha256, workspace_id


class HubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repos = self.base / "repos"
        self.repo = self.repos / "Example"
        self.repo.mkdir(parents=True)
        (self.repo / "work.txt").write_text("unsaved-to-git work")
        (self.repo / ".git").mkdir()
        (self.repo / ".git" / "marker").write_text("history")
        (self.repo / "ignored").mkdir()
        (self.repo / "ignored" / "cache.txt").write_text("ignored but included")
        self.backups = self.base / "cloud" / "Snapshots"
        self.backups.parent.mkdir()
        self.hub = Hub({"repos_root": str(self.repos), "backup_root": str(self.backups),
                        "state_dir": str(self.base / "state")})

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_archive_includes_hidden_ignored_and_symlink_without_following(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("not part of repo")
        (self.repo / "external-link").symlink_to(outside, target_is_directory=True)
        result = snapshot(self.repo, self.backups, self.base / "stage")
        self.assertEqual(sha256(result["archive"]), result["sha256"])
        with tarfile.open(result["archive"]) as archive:
            names = archive.getnames()
            self.assertIn("Example/.git/marker", names)
            self.assertIn("Example/ignored/cache.txt", names)
            self.assertEqual(archive.extractfile("Example/work.txt").read(), b"unsaved-to-git work")
            self.assertTrue(archive.getmember("Example/external-link").issym())
            self.assertNotIn("Example/external-link/secret.txt", names)

    def test_change_during_backup_does_not_publish(self):
        def change():
            (self.repo / "work.txt").write_text("changed during archive")
        with self.assertRaisesRegex(RuntimeError, "changed during"):
            snapshot(self.repo, self.backups, self.base / "stage", after_archive=change)
        self.assertFalse(list(self.backups.glob("*.tar.gz")))
        self.assertFalse(list((self.base / "stage").glob("*.tar.gz")))

    def test_unchanged_skip_and_changed_retains_old_snapshot(self):
        self.hub.backup()
        key = workspace_id("Example")
        first = self.hub.index[key]["archive"]
        self.hub.backup()
        self.assertEqual(self.hub.index[key]["archive"], first)
        (self.repo / "work.txt").write_text("newer work")
        self.hub.backup()
        self.assertNotEqual(self.hub.index[key]["archive"], first)
        self.assertTrue(Path(first).is_file())
        self.assertEqual(len(list((self.backups / key).glob("*.tar.gz"))), 2)

    def test_data_and_views_cannot_escape(self):
        key = workspace_id("Example")
        with self.assertRaises(ValueError):
            self.hub.data_path(key, "../../outside")
        with self.assertRaises(ValueError):
            self.hub.data_path("unknown", "notes")
        outside = self.base / "evil.html"
        outside.write_text("outside")
        with self.assertRaises(ValueError):
            self.hub.register_view(key, "../../evil.html", "wrong")
        (self.repo / "linked.html").symlink_to(outside)
        with self.assertRaises(ValueError):
            self.hub.register_view(key, "linked.html", "wrong")

    def test_http_json_conflicts_origin_host_and_view_boundaries(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.hub = self.hub
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        def request(path, payload=None, extra=None):
            headers = {"Origin": origin, "X-RepoHub-Token": self.hub.csrf, "Content-Type": "application/json"}
            headers.update(extra or {})
            req = urllib.request.Request(origin + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read())
        try:
            key = workspace_id("Example")
            path = f"/api/data/{key}/notes"
            empty = request(path)
            saved = request(path, {"value": {"text": "hello"}, "revision": empty["revision"]})
            self.assertEqual(request(path)["value"], {"text": "hello"})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request(path, {"value": {"text": "stale"}, "revision": empty["revision"]})
            self.assertEqual(caught.exception.code, 409)
            caught.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request(path, {"value": {}, "revision": saved["revision"]}, {"Origin": "https://other.example"})
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request('/api/status', extra={"Host": "attacker.example"})
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
            request(path, {"value": {"text": "second"}, "revision": saved["revision"]})
            self.assertEqual(len(list((self.hub.data_dir / "json-history" / key / "notes").glob("*.json"))), 1)
            (self.repo / "view.html").write_text('<!doctype html><html><head></head><body>View</body></html>')
            view = request('/api/views', {"repo_id": key, "path": "view.html", "title": "Example view"})
            with urllib.request.urlopen(origin + '/views/' + view['id'] + '/view.html') as response:
                raw = response.read()
                self.assertTrue(raw.startswith(b'<!doctype html>'))
                self.assertIn(b'/view-client.js', raw)
                self.assertIn("connect-src 'none'", response.headers['Content-Security-Policy'])
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request('/views/' + view['id'] + '/.git/marker')
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
            self.hub.backup()
            with tarfile.open(self.hub.index['repohub-data']['archive']) as archive:
                self.assertIn('data/workspaces/' + key + '/notes.json', archive.getnames())
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
