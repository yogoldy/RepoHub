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
import subprocess
import shutil
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repohub import Hub, Handler, ThreadingHTTPServer, snapshot, sha256, workspace_id, git_info, atomic_json, cloud_status, archive_manifest, content_manifest, utc_now


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
                        "state_dir": str(self.base / "state"), "retention": "latest"})

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

    def test_finder_metadata_does_not_hide_last_work_change_but_is_backed_up(self):
        work = self.repo / "work.txt"
        os.utime(work, (1000, 1000))
        os.utime(self.repo / "ignored/cache.txt", (999, 999))
        (self.repo / ".DS_Store").write_bytes(b"finder metadata")
        (self.repo / "._work.txt").write_bytes(b"metadata")
        self.hub.scan()
        self.assertEqual(self.hub.status["repos"][0]["last_changed_file"], "work.txt")
        result = snapshot(self.repo, self.backups, self.base / "stage")
        with tarfile.open(result["archive"]) as archive:
            self.assertIn("Example/.DS_Store", archive.getnames())
            self.assertIn("Example/._work.txt", archive.getnames())

    def test_change_during_backup_does_not_publish(self):
        def change():
            (self.repo / "work.txt").write_text("changed during archive")
        with self.assertRaisesRegex(RuntimeError, "changed during"):
            snapshot(self.repo, self.backups, self.base / "stage", after_archive=change)
        self.assertFalse(list(self.backups.glob("*.tar.gz")))
        self.assertFalse(list((self.base / "stage").glob("*.tar.gz")))

    def test_advanced_git_distinguishes_staged_unstaged_and_untracked(self):
        shutil.rmtree(self.repo / ".git")
        def git(*args):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git("init", "-b", "main")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "Fixture")
        (self.repo / "work.txt").write_text("unstaged")
        (self.repo / "staged.txt").write_text("staged")
        git("add", "staged.txt")
        (self.repo / "untracked.txt").write_text("untracked")
        info = git_info(self.repo)
        self.assertEqual((info["staged_files"], info["unstaged_files"], info["untracked_files"]), (1, 1, 1))

    def test_deleted_archive_is_pending_and_can_be_recreated(self):
        self.hub.backup()
        key = workspace_id("Example")
        Path(self.hub.index[key]["archive"]).unlink()
        self.hub.scan()
        self.assertTrue(self.hub.status["repos"][0]["needs_backup"])
        self.hub.backup()
        self.assertTrue(Path(self.hub.index[key]["archive"]).is_file())

    def test_unchanged_skip_and_changed_replaces_old_snapshot(self):
        self.hub.backup()
        key = workspace_id("Example")
        first = self.hub.index[key]["archive"]
        self.hub.backup()
        self.assertEqual(self.hub.index[key]["archive"], first)
        (self.repo / "work.txt").write_text("newer work")
        self.hub.backup()
        self.assertNotEqual(self.hub.index[key]["archive"], first)
        self.assertFalse(Path(first).exists())
        self.assertEqual(len(list((self.backups / key).glob("*.tar.gz"))), 1)
        with tarfile.open(self.hub.index[key]["archive"]) as archive:
            self.assertEqual(archive.extractfile("Example/work.txt").read(), b"newer work")
            self.assertIn("Example/.git/marker", archive.getnames())
            self.assertIn("Example/ignored/cache.txt", archive.getnames())

    def test_failed_replacement_preserves_previous_copy(self):
        self.hub.backup()
        key = workspace_id("Example")
        previous = self.hub.index[key].copy()
        (self.repo / "work.txt").write_text("new work")
        with patch("repohub.snapshot", side_effect=RuntimeError("copy failed")):
            self.hub.backup()
        self.assertEqual(self.hub.index[key], previous)
        self.assertTrue(Path(previous["archive"]).is_file())
        self.assertTrue(self.hub.status["backup"]["errors"])

    def test_cleanup_on_unchanged_checks_current_and_preserves_unknown_files(self):
        self.hub.backup()
        key = workspace_id("Example")
        current = Path(self.hub.index[key]["archive"])
        older = current.parent / "2000-01-01T00-00-00.000000Z.tar.gz"
        shutil.copy2(current, older)
        unknown = current.parent / "manual-backup.tar.gz"
        unknown.write_text("unmanaged")
        current.write_bytes(b"corrupt")
        with self.assertRaisesRegex(RuntimeError, "verification"):
            self.hub.retain_current(key, self.hub.index[key])
        self.assertTrue(older.is_file())
        self.assertTrue(unknown.is_file())
        shutil.copy2(older, current)
        self.hub.backup()
        self.assertFalse(older.exists())
        self.assertTrue(unknown.is_file())
        self.assertFalse(self.hub.status["backup"]["errors"])

    def test_same_size_same_mtime_edit_is_detected_and_replaced(self):
        self.hub.backup()
        key = workspace_id("Example")
        previous = self.hub.index[key]["archive"]
        path = self.repo / "work.txt"
        s = path.stat()
        path.write_bytes(b"x" * s.st_size)
        os.utime(path, ns=(s.st_atime_ns, s.st_mtime_ns))
        self.hub.scan(force=True)
        self.assertEqual(self.hub.status["repos"][0]["verification"]["state"], "different")
        self.assertTrue(self.hub.status["repos"][0]["needs_backup"])
        self.hub.backup()
        self.assertNotEqual(self.hub.index[key]["archive"], previous)
        self.assertFalse(self.hub.status["repos"][0]["needs_backup"])

    def test_corrupted_archive_detected_and_repaired(self):
        self.hub.backup()
        key = workspace_id("Example")
        Path(self.hub.index[key]["archive"]).write_bytes(b"corrupt")
        self.hub.scan(force=True)
        self.assertEqual(self.hub.status["repos"][0]["verification"]["state"], "error")
        self.hub.backup()
        self.assertFalse(self.hub.status["backup"]["errors"])
        self.assertEqual(self.hub.status["repos"][0]["verification"]["state"], "matched")

    def test_metadata_preserving_change_during_snapshot_is_rejected(self):
        path = self.repo / "work.txt"
        s = path.stat()
        def change():
            path.write_bytes(b"x" * s.st_size)
            os.utime(path, ns=(s.st_atime_ns, s.st_mtime_ns))
        with self.assertRaisesRegex(RuntimeError, "content changed"):
            snapshot(self.repo, self.backups, self.base / "stage", after_archive=change)
        self.assertFalse(list(self.backups.glob("*.tar.gz")))

    def test_archive_content_verification_includes_hardlinks_and_empty_directories(self):
        os.link(self.repo / "work.txt", self.repo / "hardlink.txt")
        (self.repo / "empty").mkdir()
        result = snapshot(self.repo, self.backups, self.base / "stage")
        self.assertEqual(archive_manifest(result["archive"], "Example"), content_manifest(self.repo))

    def test_upload_unknown_false_conflict_and_error_never_confirm_success(self):
        for raw in [{}, {"ubiquitous": True}, {"ubiquitous": False, "uploaded": True}]:
            self.assertEqual(cloud_status(raw)["state"], "unknown")
        self.assertEqual(cloud_status({"ubiquitous": True, "uploaded": False})["state"], "pending")
        self.assertEqual(cloud_status({"ubiquitous": True, "uploaded": True, "uploading": True})["state"], "uploading")
        self.assertEqual(cloud_status({"ubiquitous": True, "uploaded": True, "error": "failed"})["state"], "error")
        self.assertEqual(cloud_status({"uploaded": True, "conflicts": True})["state"], "error")
        self.assertEqual(cloud_status({"ubiquitous": True, "uploaded": True, "uploading": False})["state"], "uploaded")
        self.assertEqual(cloud_status({"error": "unreachable", "error_domain": "NSCocoaErrorDomain", "error_code": 4355})["reason"], "connection")

    def test_old_copy_kept_until_replacement_upload_is_confirmed(self):
        self.hub.config["require_upload_before_prune"] = True
        self.hub.backup()
        key = workspace_id("Example")
        old = self.hub.index[key]["archive"]
        old_record = self.hub.index[key].copy()
        (self.repo / "work.txt").write_text("new work")
        self.hub.backup()
        current = self.hub.index[key]
        self.assertTrue(Path(old).exists())
        self.hub.cloud_states[key] = {"archive": old, "state": "uploaded", "checked_at": utc_now()}
        self.hub.retain_current(key, current)
        self.assertTrue(Path(old).exists())
        with self.assertRaisesRegex(ValueError, "superseded"):
            self.hub.retain_current(key, old_record)
        self.hub.cloud_states[key] = {"archive": current["archive"], "state": "uploaded", "checked_at": utc_now()}
        self.hub.retain_current(key, current)
        self.assertFalse(Path(old).exists())

    def test_progress_and_retry_error_do_not_confirm_or_prune(self):
        raw = {"ubiquitous": True, "uploading": True, "uploaded": False,
               "percent": 100, "error": "unreachable", "error_domain": "NSCocoaErrorDomain", "error_code": 4355}
        state = cloud_status(raw)
        self.assertEqual(state["state"], "uploading")
        self.assertEqual(state["percent"], 100)
        self.assertEqual(state["last_error"], "unreachable")
        self.assertEqual(cloud_status({**raw, "conflicts": True})["state"], "error")
        self.assertEqual(cloud_status({"ubiquitous": True, "uploaded": False, "percent": 100})["state"], "pending")
        for percent in [-1, 101, float("nan"), float("inf"), True, "50", None]:
            self.assertNotIn("percent", cloud_status({"ubiquitous": True, "uploading": True, "percent": percent}))
        self.hub.config["require_upload_before_prune"] = True
        self.hub.backup()
        key = workspace_id("Example")
        old = self.hub.index[key]["archive"]
        (self.repo / "work.txt").write_text("new work")
        self.hub.backup()
        current = self.hub.index[key]
        self.hub.cloud_states[key] = {**state, "archive": current["archive"], "checked_at": utc_now()}
        self.hub.retain_current(key, current)
        self.assertTrue(Path(old).exists())

    def test_live_progress_is_replaced_by_latest_observation(self):
        self.hub.backup()
        key = workspace_id("Example")
        for percent in [42.5, 79.0]:
            response = subprocess.CompletedProcess([], 0, json.dumps({key:{"ubiquitous":True, "uploading":True, "percent":percent}}))
            with patch("repohub.subprocess.run", return_value=response):
                self.hub.refresh_cloud()
            self.assertEqual(self.hub.public_status()["repos"][0]["cloud"]["percent"], percent)
        with patch("repohub.subprocess.run", side_effect=OSError("unavailable")):
            self.hub.refresh_cloud()
        self.assertNotIn("percent", self.hub.public_status()["repos"][0]["cloud"])

    def test_failed_cloud_probe_revokes_previous_confirmation(self):
        self.hub.backup()
        key = workspace_id("Example")
        archive = self.hub.index[key]["archive"]
        self.hub.cloud_states[key] = {"archive": archive, "state": "uploaded", "checked_at": utc_now()}
        with patch("repohub.subprocess.run", side_effect=OSError("helper unavailable")):
            self.hub.refresh_cloud()
        self.assertEqual(self.hub.status["repos"][0]["cloud"]["state"], "unknown")

    def test_cleanup_refuses_external_archive_and_symlink_directory(self):
        self.hub.backup()
        key = workspace_id("Example")
        result = self.hub.index[key].copy()
        result["archive"] = str(self.base / "outside.tar.gz")
        with self.assertRaises(ValueError):
            self.hub.retain_current(key, result)
        destination = self.backups / key
        moved = self.base / "outside"
        destination.rename(moved)
        destination.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.hub.retain_current(key, self.hub.index[key])

    def test_index_publication_failure_keeps_old_copy_and_retries_cleanup(self):
        self.hub.backup()
        key = workspace_id("Example")
        previous = Path(self.hub.index[key]["archive"])
        (self.repo / "work.txt").write_text("newer work")
        def fail_cloud_index(path, value):
            if Path(path) == self.hub.backups / "index.json":
                raise OSError("index publication failed")
            atomic_json(path, value)
        with patch("repohub.atomic_json", side_effect=fail_cloud_index):
            self.hub.backup()
        self.assertTrue(previous.is_file())
        self.assertEqual(len(list(previous.parent.glob("*.tar.gz"))), 2)
        self.hub.backup()
        self.assertFalse(previous.exists())
        self.assertEqual(len(list(previous.parent.glob("*.tar.gz"))), 1)
        self.assertFalse(self.hub.status["backup"]["errors"])

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
