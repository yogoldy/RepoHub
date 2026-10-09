#!/usr/bin/env python3
"""Local repo hub: snapshots, status JSON, and scoped JSON storage for HTML views."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import tarfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

WEB = Path(__file__).parent / "web"
NAME = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-" + secrets.token_hex(6))
    try:
        with tmp.open("w", encoding="utf-8") as f:
            os.chmod(tmp, 0o600)
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def workspace_id(name):
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")[:45] or "repo"
    return slug + "-" + hashlib.sha256(name.encode()).hexdigest()[:10]


def tree_entries(root):
    root = Path(root)
    found = []
    for current, dirs, files in os.walk(root, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
        for name in dirs + files:
            path = Path(current) / name
            s = path.lstat()
            if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode)):
                raise ValueError(f"Unsupported special file: {path.relative_to(root)}")
            link = os.readlink(path) if stat.S_ISLNK(s.st_mode) else ""
            found.append((path.relative_to(root).as_posix(), s.st_mode, s.st_size, s.st_mtime_ns, link))
    return sorted(found)


def fingerprint(entries):
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_info(root):
    def run(*args):
        result = subprocess.run(["/usr/bin/git", "-C", str(root), *args], capture_output=True,
                                timeout=12, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        if result.returncode:
            return None
        return result.stdout.decode("utf-8", "replace").rstrip("\n")
    if run("rev-parse", "--is-inside-work-tree") != "true":
        return {"is_git": False, "branch": None, "changed_files": None, "last_commit": None}
    status = run("status", "--porcelain=v1", "-z", "--untracked-files=all")
    changes = []
    records = iter(status.split("\0") if status is not None else [])
    for record in records:
        if not record:
            continue
        changes.append(record[:2])
        if record[0] in "RC" or record[1] in "RC":
            next(records, None)  # Rename/copy records have a second pathname.
    return {"is_git": True, "branch": run("branch", "--show-current") or "detached HEAD",
            "changed_files": len(changes) if status is not None else None,
            "staged_files": sum(c[0] not in " ?" for c in changes) if status is not None else None,
            "unstaged_files": sum(c[1] not in " ?" for c in changes) if status is not None else None,
            "untracked_files": changes.count("??") if status is not None else None,
            "last_commit": run("log", "-1", "--format=%cI")}


def snapshot(root, destination, staging, expected=None, after_archive=None):
    """Produce a full archive; publish only if metadata stayed stable and the checksum verifies."""
    root, destination, staging = map(Path, (root, destination, staging))
    before = tree_entries(root)
    if expected is not None and fingerprint(before) != expected:
        raise RuntimeError("Repo changed before the backup started; retry later")
    staging.mkdir(parents=True, exist_ok=True)
    temporary = staging / (secrets.token_hex(12) + ".tar.gz")
    published = None
    try:
        with tarfile.open(temporary, "w:gz", compresslevel=1, dereference=False) as archive:
            archive.add(root, arcname=root.name, recursive=False)
            for relative, *_ in before:
                archive.add(root / relative, arcname=root.name + "/" + relative, recursive=False)
        if after_archive:
            after_archive()
        if before != tree_entries(root):
            raise RuntimeError("Repo changed during the backup; no snapshot was published")
        digest = sha256(temporary)
        destination.mkdir(parents=True, exist_ok=True)
        filename = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ") + ".tar.gz"
        published = destination / filename
        shutil.move(str(temporary), str(published))
        if sha256(published) != digest:
            raise RuntimeError("Snapshot checksum verification failed")
        return {"completed_at": utc_now(), "archive": str(published), "sha256": digest,
                "signature": fingerprint(before), "archive_bytes": published.stat().st_size,
                "source_files": sum(stat.S_ISREG(e[1]) for e in before),
                "source_bytes": sum(e[2] for e in before if stat.S_ISREG(e[1]))}
    except BaseException:
        if published:
            published.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


class Hub:
    def __init__(self, config):
        self.config = config
        self.root = Path(config["repos_root"]).resolve()
        self.backups = Path(config["backup_root"]).resolve()
        self.state_dir = Path(config["state_dir"]).resolve()
        if self.root == self.backups or self.root in self.backups.parents or self.root in self.state_dir.parents:
            raise ValueError("Backups and app state must be outside the source repos")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.scan_lock = threading.Lock()
        self.backup_lock = threading.Lock()
        self.csrf = secrets.token_urlsafe(32)
        self.index = load_json(self.state_dir / "backups.json", {})
        self.data_dir = self.state_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.views = load_json(self.data_dir / "views.json", [])
        self.status = {"scanned_at": None, "repos": [], "backup": {"running": False},
                       "repos_root": str(self.root), "backup_root": str(self.backups)}
        self.scan()

    def repositories(self):
        return {workspace_id(p.name): p for p in sorted(self.root.iterdir(), key=lambda p: p.name.lower())
                if p.is_dir() and not p.is_symlink() and not p.name.startswith(".")}

    def scan(self):
        if not self.scan_lock.acquire(blocking=False):
            return
        try:
            rows = []
            for key, root in self.repositories().items():
                row = {"id": key, "name": root.name, "path": str(root)}
                try:
                    entries = tree_entries(root)
                    actual = [e for e in entries if stat.S_ISREG(e[1])
                              and ".git" not in Path(e[0]).parts
                              and Path(e[0]).name != ".DS_Store"
                              and not Path(e[0]).name.startswith("._")]
                    latest = max(actual, key=lambda e: e[3], default=None)
                    row.update(git_info(root))
                    row.update({"last_file_change": datetime.fromtimestamp(latest[3] / 1e9, timezone.utc).isoformat() if latest else None,
                                "last_changed_file": latest[0] if latest else None,
                                "files": sum(stat.S_ISREG(e[1]) for e in entries),
                                "bytes": sum(e[2] for e in entries if stat.S_ISREG(e[1])),
                                "signature": fingerprint(entries)})
                except Exception as e:
                    row["error"] = str(e)
                with self.lock:
                    row["last_backup"] = self.index.get(key)
                    row["needs_backup"] = (not row.get("last_backup")
                                           or row.get("signature") != row["last_backup"].get("signature")
                                           or not Path(row["last_backup"]["archive"]).is_file())
                rows.append(row)
            with self.lock:
                self.status.update({"scanned_at": utc_now(), "repos": rows})
                self.persist_status()
        finally:
            self.scan_lock.release()

    def persist_status(self):
        atomic_json(self.state_dir / "status.json", self.status)

    def public_status(self):
        with self.lock:
            result = json.loads(json.dumps(self.status))
            result["views"] = self.views
            return result

    def backup(self):
        if not self.backup_lock.acquire(blocking=False):
            return False
        failures = []
        try:
            with self.lock:
                self.status["backup"] = {"running": True, "started_at": utc_now(), "current_repo": None}
                self.persist_status()
            if not self.backups.parent.is_dir():
                raise RuntimeError("iCloud Repository Backups folder is unavailable")
            backup_sources = {**self.repositories(), "repohub-data": self.data_dir}
            for key, root in backup_sources.items():
                with self.lock:
                    self.status["backup"]["current_repo"] = root.name
                    self.persist_status()
                try:
                    entries = tree_entries(root)
                    signature = fingerprint(entries)
                    with self.lock:
                        previous = self.index.get(key)
                    if previous and previous["signature"] == signature and Path(previous["archive"]).exists():
                        continue
                    result = snapshot(root, self.backups / key, self.state_dir / "staging", expected=signature)
                    result["name"] = root.name
                    with self.lock:
                        self.index[key] = result
                        atomic_json(self.state_dir / "backups.json", self.index)
                        atomic_json(self.backups / "index.json", self.index)
                        if key == "repohub-data":
                            self.status["data_backup"] = result
                except Exception as e:
                    failures.append({"repo": root.name, "error": str(e)})
            with self.lock:
                self.status["backup"] = {"running": False, "finished_at": utc_now(), "errors": failures,
                                         "note": "Archives verified locally. macOS manages iCloud upload."}
                self.persist_status()
        except Exception as e:
            with self.lock:
                self.status["backup"] = {"running": False, "finished_at": utc_now(), "errors": [{"error": str(e)}]}
                self.persist_status()
        finally:
            self.backup_lock.release()
            self.scan()
        return True

    def data_path(self, key, name):
        if key not in self.repositories() or not NAME.fullmatch(name):
            raise ValueError("Unknown workspace or invalid JSON name")
        return self.data_dir / "workspaces" / key / (name + ".json")

    def register_view(self, key, relative, title):
        root = self.repositories().get(key)
        if root is None:
            raise ValueError("Unknown workspace")
        path = (root / relative).resolve()
        if root not in path.parents or path.suffix.lower() not in {".html", ".htm"} or not path.is_file():
            raise ValueError("Choose an existing HTML file inside that repo")
        if any(p.startswith(".") for p in Path(relative).parts):
            raise ValueError("Hidden folders cannot be registered as views")
        item = {"id": secrets.token_hex(8), "repo_id": key, "title": str(title)[:100] or path.stem,
                "path": path.relative_to(root).as_posix()}
        with self.lock:
            self.views.append(item)
            atomic_json(self.data_dir / "views.json", self.views)
        return item


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    @property
    def hub(self):
        return self.server.hub

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def send(self, data, status=200, kind="application/json", csp=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode()
        elif isinstance(data, str):
            data = data.encode()
        self.send_response(status)
        self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", csp or "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-src 'self'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(data)

    def trusted_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.trusted_host():
            return self.send({"error": "Invalid host"}, 403)
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/api/status":
                return self.send(self.hub.public_status())
            if path == "/api/session":
                if self.headers.get("Sec-Fetch-Site") == "cross-site":
                    return self.send({"error": "Cross-site request blocked"}, 403)
                return self.send({"token": self.hub.csrf})
            if path.startswith("/api/data/"):
                parts = path.split("/")
                if len(parts) != 5:
                    raise ValueError("Invalid JSON path")
                target = self.hub.data_path(parts[3], parts[4])
                raw = target.read_bytes() if target.exists() else b"null"
                return self.send({"value": json.loads(raw), "revision": hashlib.sha256(raw).hexdigest()})
            if path.startswith("/views/"):
                return self.serve_view(path)
            routes = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css",
                      "/view-client.js": "view-client.js", "/notes.html": "notes.html"}
            if path not in routes:
                return self.send({"error": "Not found"}, 404)
            target = WEB / routes[path]
            kind = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if path == "/notes.html":
                return self.send(target.read_bytes(), kind=kind, csp=self.view_csp())
            return self.send(target.read_bytes(), kind=kind)
        except (ValueError, OSError) as e:
            return self.send({"error": str(e)}, 400)

    def view_csp(self):
        return f"default-src 'none'; script-src 'unsafe-inline' {self.origin}; style-src 'unsafe-inline' {self.origin}; img-src data: blob: {self.origin}; font-src {self.origin}; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'self'; frame-ancestors {self.origin}"

    def serve_view(self, path):
        parts = path.split("/", 3)
        view = next((v for v in self.hub.views if v["id"] == parts[2]), None)
        if not view:
            return self.send({"error": "Unknown view"}, 404)
        root = self.hub.repositories().get(view["repo_id"])
        if root is None:
            return self.send({"error": "Repo unavailable"}, 404)
        relative = parts[3] if len(parts) == 4 else view["path"]
        target = (root / relative).resolve()
        extensions = {".html", ".htm", ".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico", ".woff", ".woff2"}
        if root not in target.parents or target.suffix.lower() not in extensions or any(p.startswith(".") for p in Path(relative).parts):
            return self.send({"error": "Asset path blocked"}, 403)
        raw = target.read_bytes()
        if len(raw) > 20 * 1024 * 1024:
            return self.send({"error": "Asset is too large"}, 413)
        if target.suffix.lower() in {".html", ".htm"}:
            injection = b'<script src="/view-client.js"></script>'
            if re.search(br"<head[^>]*>", raw, re.I):
                raw = re.sub(br"(<head[^>]*>)", lambda m: m[0] + injection, raw, count=1, flags=re.I)
            else:
                raw = re.sub(br"^(<!doctype[^>]*>)?", lambda m: m[0] + injection, raw, count=1, flags=re.I)
        return self.send(raw, kind=mimetypes.guess_type(str(target))[0] or "application/octet-stream", csp=self.view_csp())

    def do_POST(self):
        if not self.trusted_host() or self.headers.get("Origin") != self.origin or self.headers.get("X-RepoHub-Token") != self.hub.csrf:
            return self.send({"error": "Request blocked"}, 403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 2 * 1024 * 1024:
                return self.send({"error": "JSON is too large"}, 413)
            payload = json.loads(self.rfile.read(size) or b"{}")
            path = unquote(urlparse(self.path).path)
            if path == "/api/backup":
                threading.Thread(target=self.hub.backup, daemon=True).start()
                return self.send({"accepted": True}, 202)
            if path == "/api/scan":
                threading.Thread(target=self.hub.scan, daemon=True).start()
                return self.send({"accepted": True}, 202)
            if path == "/api/views":
                return self.send(self.hub.register_view(payload["repo_id"], payload["path"], payload.get("title", "")), 201)
            if path.startswith("/api/data/"):
                parts = path.split("/")
                if len(parts) != 5:
                    raise ValueError("Invalid JSON path")
                target = self.hub.data_path(parts[3], parts[4])
                with self.hub.lock:
                    raw = target.read_bytes() if target.exists() else b"null"
                    revision = hashlib.sha256(raw).hexdigest()
                    if payload.get("revision") != revision:
                        return self.send({"error": "This JSON changed since you loaded it. Reload before saving."}, 409)
                    if target.exists():
                        history = self.hub.data_dir / "json-history" / parts[3] / parts[4]
                        history.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target, history / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f") + ".json"))
                    atomic_json(target, payload["value"])
                    return self.send({"revision": hashlib.sha256(target.read_bytes()).hexdigest()})
            return self.send({"error": "Not found"}, 404)
        except (ValueError, KeyError, OSError) as e:
            return self.send({"error": str(e)}, 400)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--backup-once", action="store_true")
    args = parser.parse_args()
    config = load_json(args.config, None)
    if not config:
        raise SystemExit("Missing configuration")
    hub = Hub(config)
    if args.backup_once:
        hub.backup()
        return
    server = ThreadingHTTPServer(("127.0.0.1", config.get("port", 8767)), Handler)
    server.hub = hub
    def scans():
        while True:
            time.sleep(config.get("scan_seconds", 30))
            try:
                hub.scan()
            except Exception as e:
                print("Scan failed:", e, flush=True)
    def backups():
        while True:
            hub.backup()
            time.sleep(config.get("backup_seconds", 3600))
    threading.Thread(target=scans, daemon=True).start()
    threading.Thread(target=backups, daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
