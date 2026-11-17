#!/usr/bin/env python3
"""Local repo hub: snapshots, status JSON, and scoped JSON storage for HTML views."""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import signal
import shutil
import stat
import subprocess
import tarfile
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as StandardThreadingHTTPServer
from socketserver import TCPServer
from urllib.parse import unquote, urlparse
import urllib.request
from backup_policy import BackupScheduler, default_settings, validate_settings, power_source, project_schedule
from status_health import annotate_health, ProblemTracker, age, backup_location
from diagnostics import DiagnosticLog, diagnostic_ref
from update_evidence import update_evidence
from backup_lifecycle import BackupLifecycle
from change_evidence import ChangeEvidence
from backup_changes import finder_only_difference, edit_entries
from access_checks import access_failure, probe_source, probe_destination
from workspace_registry import WorkspaceRegistry, workspace_id, require_source, overlaps
from backup_layout import BackupLayout, LayoutTransaction
from destination_policy import require_destination
from git_discovery import GitDiscovery
import outside_items
from outside_items import OutsideChoices
from setup_service import SetupService
from report_preview import preview_report
from report_delivery import send_report, connection_status, delivery_status, case_path, read_private

WEB = Path(__file__).parent / "web"
NAME = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
ARCHIVE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.\d{6}Z\.tar\.gz$")
LINKED = "::linked::"  # Upload-status IDs for included-folder archives.
CHECKOUT = "::checkout::"  # Upload-status IDs for included-checkout archives.
KEPT = {"linked": "linked:", "checkouts": "checkout:"}
KEPT_FIELDS = {"kind", "name", "reason", "removed_at", "keep_until"}
KEEP_WINDOW = timedelta(days=30)  # Authorized automatic deletion window for removed outside items.


def source_unreachable(path):
    """True when an outside folder can't be reached now, as opposed to having been deleted.

    A folder on a drive under /Volumes that isn't mounted, or one that exists but can't be
    read, may come back. Its last backup must not start the deletion countdown: an
    unplugged or failed drive is exactly when that backup matters.
    """
    if not path:
        return False
    try:
        os.stat(path)
    except FileNotFoundError:
        parts = Path(path).parts
        if len(parts) > 2 and parts[1] == "Volumes":
            return not os.path.ismount(os.path.join("/", parts[1], parts[2]))
        return False
    except OSError:
        return True  # Present but unreadable (permissions, I/O error): not deleted.
    return False


def set_outside(entry, outside):
    """Record a repo's included linked folders, checkouts and kept items on its index entry."""
    for field in ("linked", "checkouts", "removed"):
        if outside.get(field):
            entry[field] = outside[field]
        else:
            entry.pop(field, None)


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
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        tmp.unlink(missing_ok=True)


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def atomic_json_if_changed(path, value):
    try:
        if load_json(path, None) == value:
            return False
    except (ValueError, OSError):
        pass
    atomic_json(path, value)
    return True


def tree_entries(root):
    root = Path(root)
    require_source(root)
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


class SourceChanged(RuntimeError):
    """The source was unstable; retry without blaming or replacing its backup."""


def content_manifest(root, entries=None):
    """Hash every regular file; do not reuse digests based on size or timestamps."""
    root = Path(root)
    entries = tree_entries(root) if entries is None else entries
    result = {}
    for relative, mode, size, _, link in entries:
        item = {"mode": stat.S_IMODE(mode)}
        if stat.S_ISREG(mode):
            h = hashlib.sha256()
            fd = os.open(root / relative, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as f:
                before = os.fstat(f.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise SourceChanged("File type changed during verification")
                for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
                    h.update(block)
                after = os.fstat(f.fileno())
                if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise SourceChanged("File changed during content verification")
            item.update(kind="file", size=before.st_size, sha256=h.hexdigest())
        elif stat.S_ISDIR(mode):
            item.update(kind="directory")
        else:
            item.update(kind="symlink", target=link)
        result[relative] = item
    if entries != tree_entries(root):
        raise SourceChanged("Repo changed during content verification; retry later")
    return result


def archive_manifest(path, root_name):
    """Read all stored file bytes without extracting; validate paths and link records."""
    result = {}
    prefix = root_name + "/"
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            if member.name == root_name and member.isdir():
                continue
            if not member.name.startswith(prefix):
                raise RuntimeError("Unexpected archive root")
            relative = member.name[len(prefix):]
            if not relative or ".." in Path(relative).parts or relative in result:
                raise RuntimeError("Unsafe or duplicate archive entry")
            item = {"mode": member.mode}
            if member.isfile():
                h = hashlib.sha256()
                with archive.extractfile(member) as f:
                    for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
                        h.update(block)
                item.update(kind="file", size=member.size, sha256=h.hexdigest())
            elif member.islnk():
                target = result.get(member.linkname[len(prefix):]) if member.linkname.startswith(prefix) else None
                if not target or target["kind"] != "file":
                    raise RuntimeError("Invalid archive hardlink")
                item.update(kind="file", size=target["size"], sha256=target["sha256"])
            elif member.isdir():
                item.update(kind="directory")
            elif member.issym():
                item.update(kind="symlink", target=member.linkname)
            else:
                raise RuntimeError("Unsupported archive entry")
            result[relative] = item
    return result


def content_signature(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def archive_stamp(path):
    s = Path(path).stat()
    return [s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def summarize_changes(source, saved):
    """Describe hash/path/mode differences without calling background writes user edits."""
    counts = {"finder_metadata": 0, "git_data": 0, "repo_files": 0}
    samples = {category: [] for category in counts}
    for relative in sorted(source.keys() | saved.keys()):
        if source.get(relative) == saved.get(relative):
            continue
        path = Path(relative)
        category = ("finder_metadata" if path.name == ".DS_Store" or path.name.startswith("._")
                    else "git_data" if ".git" in path.parts else "repo_files")
        counts[category] += 1
        if len(samples[category]) < 8:
            samples[category].append({"path": relative, "category": category,
                                     "change": "added" if relative not in saved else "removed" if relative not in source else "modified"})
    # Include representatives of each category so Git internals cannot hide repo files.
    examples = [item for group in samples.values() for item in group[:2]]
    extras = [item for group in samples.values() for item in group[2:]]
    examples.extend(extras[:8 - len(examples)])
    return {"counts": counts, "examples": examples}


def verify_current(root, current):
    entries = tree_entries(root)
    source = content_manifest(root, entries)
    source_digest = content_signature(source)
    stamp = archive_stamp(current["archive"])
    if sha256(current["archive"]) != current["sha256"]:
        raise RuntimeError("Backup archive checksum failed; replacement required")
    saved = None
    stored_digest = current.get("content_signature")
    if not stored_digest:
        saved = archive_manifest(current["archive"], Path(root).name)
        stored_digest = content_signature(saved)
    changes = {}
    ignored_finder_only = False
    if source_digest != stored_digest:
        if saved is None:
            saved = archive_manifest(current["archive"], Path(root).name)
        changes = summarize_changes(source, saved)
        ignored_finder_only = finder_only_difference(source, saved)
    if entries != tree_entries(root):
        raise SourceChanged("Files changed while verifying; retry later")
    if stamp != archive_stamp(current["archive"]):
        raise RuntimeError("Backup archive changed while verifying; retry later")
    return {"state": "matched" if source_digest == stored_digest else "different",
            "checked_at": utc_now(), "signature": fingerprint(entries),
            "archive": current["archive"], "archive_stamp": stamp,
            "content_signature": source_digest, "archive_content_signature": stored_digest,
            "changes": changes, "ignored_finder_only": ignored_finder_only,
            "backup_required": source_digest != stored_digest and not ignored_finder_only}


def cloud_status(raw):
    percent = raw.get("percent")
    progress = ({"percent": percent, "progress_source": "macOS published progress"}
                if type(percent) in (int, float) and math.isfinite(percent) and 0 <= percent <= 100 else {})
    if raw.get("ubiquitous") is True and raw.get("uploading") is True and raw.get("conflicts") is not True:
        result = {"state": "uploading", **progress}
        if raw.get("error"):
            result.update(last_error=raw["error"], error_code=raw.get("error_code"),
                          detail="macOS reports an upload in progress; it also reports: " + raw["error"])
        return result
    if raw.get("error") or raw.get("conflicts") is True:
        reason = ("connection" if raw.get("error_domain") == "NSCocoaErrorDomain" and raw.get("error_code") == 4355
                  else "storage" if raw.get("error_domain") == "NSCocoaErrorDomain" and raw.get("error_code") == 4354
                  else "conflict" if raw.get("conflicts") is True else "other")
        return {"state": "error", "detail": raw.get("error") or "iCloud has unresolved conflicts",
                "reason": reason, "error_code": raw.get("error_code")}
    if raw.get("ubiquitous") is not True:
        return {"state": "unknown", "detail": "macOS did not identify this as an iCloud item"}
    if raw.get("uploading") is True:
        return {"state": "uploading"}
    if raw.get("uploaded") is True:
        return {"state": "uploaded", "detail": "Upload confirmed by macOS"}
    if raw.get("uploaded") is False:
        return {"state": "pending", **progress}
    return {"state": "unknown", "detail": "macOS did not return upload completion"}


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


def snapshot(root, destination, staging, expected=None, after_archive=None, observe=None, source_check=None):
    """Verify source bytes, stored archive contents, and destination checksum before publication."""
    root, destination, staging = map(Path, (root, destination, staging))
    observe = observe or (lambda stage: None)
    source_check = source_check or (lambda: None)
    source_check()
    observe("source_hashing")
    before = tree_entries(root)
    if expected is not None and fingerprint(before) != expected:
        raise RuntimeError("Repo changed before the backup started; retry later")
    contents = content_manifest(root, before)
    staging.mkdir(parents=True, exist_ok=True)
    temporary = staging / (secrets.token_hex(12) + ".tar.gz")
    published = None
    try:
        observe("archive_creation")
        with tarfile.open(temporary, "w:gz", compresslevel=1, dereference=False) as archive:
            archive.add(root, arcname=root.name, recursive=False)
            for relative, *_ in before:
                archive.add(root / relative, arcname=root.name + "/" + relative, recursive=False)
        if after_archive:
            after_archive()
        source_check()
        if before != tree_entries(root):
            raise RuntimeError("Repo changed during the backup; no snapshot was published")
        observe("archive_verification")
        if archive_manifest(temporary, root.name) != contents or content_manifest(root) != contents:
            raise RuntimeError("Repo content changed during the backup; no snapshot was published")
        source_check()
        digest = sha256(temporary)
        destination.mkdir(parents=True, exist_ok=True)
        filename = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ") + ".tar.gz"
        published = destination / filename
        observe("archive_transfer")
        shutil.move(str(temporary), str(published))
        observe("destination_verification")
        if sha256(published) != digest:
            raise RuntimeError("Snapshot checksum verification failed")
        source_check()
        return {"completed_at": utc_now(), "archive": str(published), "sha256": digest,
                "signature": fingerprint(before), "content_signature": content_signature(contents),
                "archive_bytes": published.stat().st_size,
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
        config = dict(config)
        self.state_dir = Path(config['state_dir']).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        recovered_setup = LayoutTransaction(self.state_dir, atomic_json).recover()
        self.setup_record = load_json(self.state_dir / 'data/setup.json', {})
        if self.setup_record.get('destination'):
            config['backup_root'] = self.setup_record['destination']['path']
        self.configured = self.setup_record.get('configured', not config.get('setup_required', False))
        self.setup_recovery_required = False
        self.setup_cloud_root = config.get('_setup_test_cloud_root')
        self.config = config
        self.retention = config.get("retention", "all")
        if self.retention not in {"all", "latest"}:
            raise ValueError("Unknown backup retention policy")
        self.root = Path(config["repos_root"]).resolve() if config.get("repos_root") else None
        self.backups = Path(config["backup_root"]).resolve()
        self.state_dir = Path(config["state_dir"]).resolve()
        # Once migrated, the registry is authoritative; the legacy repo-home
        # setting must not block an unrelated saved manual selection.
        if not (self.state_dir / "data/workspace-registry.json").exists() and self.root is not None and (overlaps(self.root, self.backups) or overlaps(self.root, self.state_dir)):
            raise ValueError("Backups and app state must be outside the source repos")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.diagnostics = DiagnosticLog(self.state_dir / "diagnostics")
        if recovered_setup:
            self.diagnostics.emit('setup_recovery', result='complete')
        self.diagnostics.emit("helper_started", build_id=sha256(Path(__file__))[:16])
        self.evidence = ChangeEvidence(self.diagnostics)
        self.lifecycle = BackupLifecycle(self.diagnostics)
        self.lock = threading.RLock()
        self.scan_lock = threading.Lock()
        self.full_scan_progress_at = None
        self.backup_lock = threading.Lock()
        self.csrf = secrets.token_urlsafe(32)
        self.readiness = None
        self.readiness_running = False
        self.readiness_result = 'unchecked'
        self.verifications = {}
        self.cloud_states = {}
        self.index = load_json(self.state_dir / "backups.json", {})
        self.data_dir = self.state_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.registry = WorkspaceRegistry(self.data_dir / "workspace-registry.json", self.root,
                                          (self.backups, self.state_dir,
                                           *(Path(path) for path in self.setup_record.get('previous_destinations', []))), atomic_json,
                                          config.get('sources', {'mode': 'manual', 'paths': []}))
        self.layout = BackupLayout(self.state_dir, self.backups)
        self.setup = SetupService(self, atomic_json)
        self.archive_digest = sha256
        self.discovery = GitDiscovery((self.backups, self.state_dir,
                                       *(Path(path) for path in self.setup_record.get('previous_destinations', []))),
                                      diagnostics=self.diagnostics)
        self.settings_path = self.data_dir / "settings.json"
        self.settings = validate_settings(load_json(self.settings_path, default_settings()))
        if not self.settings_path.exists():
            atomic_json(self.settings_path, self.settings)
        self.repo_settings_path = self.data_dir / "repo-settings.json"
        self.repo_settings = {key: validate_settings(value) for key, value in
                              load_json(self.repo_settings_path, {}).items()}
        if not self.repo_settings_path.exists():
            atomic_json(self.repo_settings_path, self.repo_settings)
        self.outside_choices = OutsideChoices(self.data_dir / "outside-choices.json", atomic_json)
        self.outside_detected = {}
        saved_clock = load_json(self.state_dir / "schedule-clock.json", {})
        previous_times = [datetime.fromisoformat(item["completed_at"]).timestamp() for item in self.index.values()]
        self.last_periodic_at = saved_clock.get("last_periodic_at", max(previous_times, default=0))
        self.repo_periodic_at = saved_clock.get("repos", {})
        self.scheduler = BackupScheduler(time.monotonic() - max(0, time.time() - self.last_periodic_at))
        self.problem_tracker = ProblemTracker(load_json(self.state_dir / "problem-episodes.json", {}))
        self.power = "unknown"
        self.views = load_json(self.data_dir / "views.json", [])
        previous_backup = load_json(self.state_dir / "status.json", {}).get("backup", {})
        self.previous_backup_run = previous_backup.get("run_id")
        if previous_backup.get("running"):
            self.lifecycle.emit("backup_interrupted", run_id=self.previous_backup_run, reason="helper_restarted", result="unobserved_completion")
        self.status = {"scanned_at": None, "repos": [], "backup": {"running": False},
                       "repos_root": str(self.root) if self.root else None, "backup_root": str(self.backups)}
        self.scan(deep=False)

    def repositories(self):
        return self.registry.refresh()

    def readiness_status(self):
        with self.lock:
            result = json.loads(json.dumps(self.readiness or {'checked_at':None,'sources':[], 'destination':{'state':'unchecked'},'background':{'helper':'running','login':'unknown'}}))
            result['running'] = self.readiness_running
            result['result'] = self.readiness_result
            result['notifications'] = load_json(self.state_dir/'notifications.json', {'permission':'unknown'})
            return result

    def start_readiness(self):
        with self.lock:
            if self.readiness_running:raise FileExistsError('Access check already running')
            self.readiness_running = True
            self.readiness_result = "checking"
        threading.Thread(target=self.check_readiness, daemon=True).start()
        return self.readiness_status()

    def check_readiness(self):
        started = time.monotonic()
        if not self.backup_lock.acquire(blocking=False):
            with self.lock:self.readiness_running = False;self.readiness_result = "deferred"
            self.diagnostics.emit('access_readiness', result='deferred', reason='backup_busy')
            return
        if not self.scan_lock.acquire(blocking=False):
            self.backup_lock.release()
            with self.lock:self.readiness_running = False;self.readiness_result = "deferred"
            self.diagnostics.emit('access_readiness', result='deferred', reason='scan_error')
            return
        try:
            sources = []
            for key, path in self.repositories().items():
                try:
                    self.registry.require_workspace(key, path);probe_source(path)
                    self.registry.require_workspace(key, path)
                    outcome = {'state':'accessible','operation':'source_read'}
                except OSError as error:outcome = access_failure(error,'source_read')
                sources.append({'id':key,'name':path.name, **outcome})
                self.diagnostics.emit('access_readiness', repo_ref=diagnostic_ref(key), state=outcome['state'], operation='source_read', error_code=outcome.get('error_code'),result='complete')
            try:
                # Probe the existing destination root; never create a missing mounted path.
                if self.setup_record.get('destination'):
                    require_destination(self.setup_record['destination'])
                probe_destination(self.backups if self.backups.exists() else self.backups.parent)
                destination = {'state':'accessible','operation':'destination_write'}
            except OSError as error:destination = access_failure(error,'destination_write')
            login = 'unknown'
            try:
                registration = subprocess.run(['/bin/launchctl','print',f'gui/{os.getuid()}/com.leogoldberg.repohub.service'],capture_output=True,text=True,timeout=3)
                login = 'registered' if registration.returncode == 0 and str(self.state_dir) in registration.stdout else 'not_registered'
            except (OSError,subprocess.SubprocessError):pass
            with self.lock:self.readiness_result = 'complete';self.readiness = {'checked_at':utc_now(),'sources':sources,'destination':destination,'background':{'helper':'running','login':login}}
            self.diagnostics.emit('access_readiness', operation='destination_write',state=destination['state'],result='complete',error_code=destination.get('error_code'),duration_ms=(time.monotonic()-started)*1000)
        except Exception as error:
            with self.lock:self.readiness_result = 'failed'
            self.diagnostics.emit('access_readiness',result='failed',error_type=type(error).__name__)
        finally:
            self.scan_lock.release();self.backup_lock.release()
            with self.lock:self.readiness_running = False

    def workspace_status(self):
        return self.registry.status()

    def preview_workspaces(self, payload):
        if set(payload) != {"source", "revision"}:
            raise ValueError("Invalid workspace review request")
        try:
            result = self.registry.review(payload["source"], payload["revision"])
        except (ValueError, OSError):
            self.diagnostics.emit("workspace_review", result="failed")
            raise
        self.diagnostics.emit("workspace_review", result="complete", mode=payload["source"]["mode"],
                              repo_count=len(result["workspaces"]))
        return result

    def save_workspaces(self, payload):
        try:
            return self._save_workspaces(payload)
        except (ValueError, OSError):
            self.diagnostics.emit("workspace_configuration", result="failed")
            raise

    def _save_workspaces(self, payload):
        if set(payload) not in ({"source", "revision"}, {"source", "revision", "review"}):
            raise ValueError("Invalid workspace configuration request")
        if "review" in payload and (not isinstance(payload["review"], str) or not re.fullmatch(r"[0-9a-f]{64}", payload["review"])):
            raise ValueError("Review the folder selection before saving")
        if not self.backup_lock.acquire(blocking=False):
            raise FileExistsError("A backup is running. Try after it finishes.")
        try:
            if not self.scan_lock.acquire(blocking=False):
                raise FileExistsError("A scan is running. Try after it finishes.")
            try:
                result = self.registry.save(payload["source"], payload["revision"], payload.get("review"))
                self.diagnostics.emit("workspace_configuration", result="saved", mode=result["configuration"]["source"]["mode"],
                                      repo_count=sum(r["active"] for r in result["configuration"]["workspaces"]))
            finally:
                self.scan_lock.release()
        finally:
            self.backup_lock.release()
        self.scan(deep=False)
        return result

    def request_selected_action(self, action, payload):
        """Admit an explicit reviewed selection before starting any worker."""
        if action not in {"backup", "scan"} or set(payload) != {"repo_ids", "revision"}:
            raise ValueError("Choose repositories and review the selection again")
        keys = payload["repo_ids"]
        if (not isinstance(keys, list) or not keys or len(keys) > 1000
                or any(not isinstance(key, str) for key in keys)
                or len(set(keys)) != len(keys)):
            raise ValueError("Choose one or more distinct repositories")
        if not self.configured or self.setup_recovery_required:
            raise ValueError("Finish setup before starting this action")
        if not self.backup_lock.acquire(blocking=False):
            raise FileExistsError("A backup is running. Try after it finishes.")
        scan_reserved = False
        handed_off = False
        try:
            if not self.scan_lock.acquire(blocking=False):
                raise FileExistsError("A scan is running. Try after it finishes.")
            scan_reserved = True
            current = self.registry.status()
            if payload["revision"] != current["revision"]:
                raise FileExistsError("Folder selection changed. Choose repositories again.")
            sources = {row["id"]: Path(row["path"]) for row in
                       current["configuration"]["workspaces"] if row["active"]}
            for key in keys:
                if key not in sources:
                    raise ValueError("A selected repository is no longer monitored")
                if action == "backup":
                    require_source(sources[key], canonical_only=True)
                    self.registry.require_workspace(key, sources[key])
            options = {"keys": list(keys), "_lock_held": True} if action == "backup" else {
                "repo_ids": list(keys), "force": True, "_lock_held": True}
            worker = threading.Thread(target=self.backup if action == "backup" else self.scan,
                                      kwargs=options, daemon=True)
            worker.start()
            handed_off = True
        finally:
            if scan_reserved and (action == "backup" or not handed_off):
                self.scan_lock.release()
            if action == "scan" or not handed_off:
                self.backup_lock.release()
        return {"accepted": True, "repo_ids": list(keys)}

    def retry_check(self, repo_id):
        if not isinstance(repo_id, str) or repo_id not in self.repositories():
            raise ValueError("Unknown repo")
        if not self.scan_lock.acquire(blocking=False):
            raise FileExistsError("A check is already running. We'll check again on the next scan.")
        self.diagnostics.emit("scan_retry_requested", repo_ref=diagnostic_ref(repo_id), reason="manual")
        worker = threading.Thread(target=self.scan, kwargs={"force": True, "repo_id": repo_id, "_lock_held": True}, daemon=True)
        try:
            worker.start()
        except BaseException:
            self.scan_lock.release()
            raise

    def scan(self, deep=True, force=False, repo_id=None, _lock_held=False, repo_ids=None):
        if self.setup_recovery_required:
            if _lock_held:
                self.scan_lock.release()
            return
        if not _lock_held and not self.scan_lock.acquire(blocking=False):
            return
        selected_keys = set(repo_ids) if repo_ids is not None else ({repo_id} if repo_id is not None else None)
        scan_id, scan_started = secrets.token_hex(8), time.monotonic()
        scan_complete = False
        if selected_keys is None:
            with self.lock:
                self.full_scan_progress_at = utc_now()
        self.diagnostics.emit("scan_started", scan_id=scan_id, mode="content" if deep else "metadata", reason="forced" if force else "poll")
        try:
            previous_rows = {row["id"]: row for row in self.status["repos"]}
            rows = []
            for key, root in self.repositories().items():
                if selected_keys is not None and key not in selected_keys:
                    if key in previous_rows:
                        rows.append(previous_rows[key])
                    continue
                repo_started = time.monotonic()
                verification_performed = False
                row = {"id": key, "name": root.name, "path": str(root),
                       "scan_id": scan_id, "scan_checked_at": utc_now()}
                try:
                    require_source(root, canonical_only=True)
                    if key != "repohub-data":self.registry.require_workspace(key, root)
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
                                "signature": fingerprint(entries), "edit_signature": fingerprint(edit_entries(entries))})
                    row["outside"] = self.detect_outside(key, root, entries)
                except Exception as e:
                    self.outside_detected.pop(key, None)
                    row["error"] = str(e)
                    if isinstance(e, OSError):
                        row["access"] = access_failure(e, "source_read")
                        row["error"] = row["access"]["detail"]
                with self.lock:
                    row["last_backup"] = self.index.get(key)
                    cached = self.verifications.get(key, {})
                    row["needs_backup"] = (not row.get("last_backup")
                                           or row.get("signature") != row["last_backup"].get("signature")
                                           or not Path(row["last_backup"]["archive"]).is_file())
                current = row["last_backup"]
                valid = False
                if current and not row.get("error"):
                    try:
                        age = time.time() - datetime.fromisoformat(cached.get("checked_at", "1970-01-01T00:00:00+00:00")).timestamp()
                        valid = (cached.get("archive") == current["archive"]
                                 and cached.get("signature") == row.get("signature")
                                 and cached.get("archive_stamp") == archive_stamp(current["archive"])
                                 and age < self.config.get("verification_seconds", 900))
                        if deep and (force or not valid):
                            verification_performed = True
                            with self.lock:
                                self.status["verifying"] = root.name
                                self.persist_status()
                            cached = verify_current(root, current)
                            with self.lock:
                                self.verifications[key] = cached
                            valid = cached.get("signature") == row.get("signature")
                    except SourceChanged:
                        cached = {"state": "changing", "checked_at": utc_now(),
                                  "reason": "source_changed_during_verification"}
                        valid = True
                    except Exception as e:
                        cached = {"state": "error", "checked_at": utc_now(), "error": str(e)}
                        if isinstance(e, OSError):
                            cached["access"] = access_failure(e, "verification_read")
                            cached["error"] = cached["access"]["detail"]
                        valid = True
                row["verification"] = cached if valid else {"state": "checking"}
                if row["verification"]["state"] == "matched":
                    # Timestamps/sizes of directories are hints, not content differences.
                    # This cached receipt is bound to the current tree and archive above.
                    row["needs_backup"] = False
                if row["verification"]["state"] == "different":
                    row["needs_backup"] = row["verification"].get("backup_required", True)
                if row["verification"]["state"] == "error":
                    row["needs_backup"] = True
                if current and not self.layout.contains(key, current['archive']):
                    row['needs_backup'] = True
                    row['verification'] = {'state': 'missing'}
                if not row.get("error"):
                    included = self.included_state(key, root, current)
                    if any(included.values()):
                        row["included_folders"] = included
                        if included["pending"]:
                            row["needs_backup"] = True
                            row["linked_pending"] = True
                row["cloud"] = self.cloud_for(key, current)
                self.evidence.repo_checked(row, scan_id, (time.monotonic() - repo_started) * 1000, not verification_performed)
                rows.append(row)
                # Publish only completed checks; never refresh the timestamps of
                # other folders while a slow source is still being examined.
                with self.lock:
                    if selected_keys is None:
                        self.full_scan_progress_at = utc_now()
                    current_rows = self.status["repos"]
                    for index, current_row in enumerate(current_rows):
                        if current_row["id"] == key:
                            current_rows[index] = row
                            break
                    else:
                        current_rows.append(row)
            with self.lock:
                self.scheduler.observe(rows, time.monotonic())
                self.status.update({"scan_id": scan_id, "repos": rows,
                                    "source_mode": self.registry.value["source"]["mode"],
                                    "repos_root": self.registry.value["source"].get("home"),
                                    "workspace_sources": [{"id": row["id"], "path": row["path"]} for row in rows]})
                if selected_keys is None:
                    self.status["scanned_at"] = utc_now()
                self.status["verifying"] = None
                self.persist_status()
                scan_complete = True
        finally:
            self.diagnostics.emit("scan_finished", scan_id=scan_id, result="complete" if scan_complete else "failed",
                                  duration_ms=(time.monotonic() - scan_started) * 1000)
            with self.lock:
                self.status["verifying"] = None
                if selected_keys is None:
                    self.full_scan_progress_at = None
            self.scan_lock.release()

    def persist_status(self):
        atomic_json(self.state_dir / "status.json", self.status)

    def public_status(self):
        with self.lock:
            result = json.loads(json.dumps(self.status))
            result["views"] = self.views
            result["notifications"] = load_json(self.state_dir / "notifications.json", {"permission": "unknown"})
            result["settings"] = self.settings
            result['setup'] = {'configured': self.configured,
                               'reviewed': self.setup_record.get('reviewed', False),
                               'recovery_required': self.setup_recovery_required}
            wall_now, monotonic_now = time.time(), time.monotonic()
            for row in result["repos"]:
                row["schedule_override"] = row["id"] in self.repo_settings
                row["backup_settings"] = self.repo_settings.get(row["id"], self.settings)
                row["schedule_evidence"] = project_schedule(
                    self.scheduler, self.settings, self.power, row, wall_now, monotonic_now,
                    self.last_periodic_at, self.repo_periodic_at,
                    busy=self.backup_lock.locked(), overrides=self.repo_settings)
                row["backup_location"] = backup_location(
                    row, wall_now, max(45, self.config.get("cloud_seconds", 5) * 6))
            if hasattr(self, "application_release"):
                result["application_release"] = dict(self.application_release)
                update = update_evidence(load_json(self.state_dir / "update-status.json", {}), self.application_release)
                result["application_update"] = update
                if update and update != getattr(self, "last_update_evidence", None):
                    self.diagnostics.emit("application_update", **update,
                                          build_id=diagnostic_ref(self.application_release["source_revision"]))
                    self.last_update_evidence = update
            result["power_source"] = self.power
            result["full_scan_progress_at"] = self.full_scan_progress_at
            result["observed_at"] = utc_now()
            result["diagnostics"] = self.diagnostics.status()
            annotate_health(result, self.config, time.time())
            result["diagnostic_observation_id"] = self.evidence.observe_status(result)
            before = json.dumps(self.problem_tracker.episodes, sort_keys=True)
            result["problems"] = self.problem_tracker.update(result, time.time())
            if before != json.dumps(self.problem_tracker.episodes, sort_keys=True):
                atomic_json(self.state_dir / "problem-episodes.json", self.problem_tracker.episodes)
            return result

    def settings_status(self):
        with self.lock:
            return {"settings": json.loads(json.dumps(self.settings)),
                    "revision": sha256(self.settings_path), "power_source": self.power}

    def save_settings(self, payload):
        value = validate_settings(payload.get("settings"))
        with self.lock:
            if payload.get("revision") != sha256(self.settings_path):
                raise FileExistsError("Settings changed. Reopen settings before saving.")
            atomic_json(self.settings_path, value)
            self.settings = value
            return self.settings_status()

    def repo_settings_status(self, key):
        with self.lock:
            if key not in self.repositories():
                raise ValueError("Unknown repository")
            return {"settings": json.loads(json.dumps(self.repo_settings.get(key, self.settings))),
                    "defaults": json.loads(json.dumps(self.settings)),
                    "override": key in self.repo_settings,
                    "revision": sha256(self.repo_settings_path),
                    "defaults_revision": sha256(self.settings_path), "power_source": self.power}

    def save_repo_settings(self, key, payload):
        if set(payload) != {"settings", "revision", "defaults_revision"}:
            raise ValueError("Invalid repository settings request")
        value = None if payload["settings"] is None else validate_settings(payload["settings"])
        with self.lock:
            self.repo_settings_status(key)  # Validate the exact current workspace ID.
            if (payload["revision"] != sha256(self.repo_settings_path)
                    or payload["defaults_revision"] != sha256(self.settings_path)):
                raise FileExistsError("Settings changed. Reopen this schedule before saving.")
            updated = dict(self.repo_settings)
            if value is None:
                updated.pop(key, None)
            else:
                updated[key] = value
            atomic_json(self.repo_settings_path, updated)
            self.repo_settings = updated
            return self.repo_settings_status(key)

    def detect_outside(self, key, root, entries):
        """Report outside items; detection never changes backup status."""
        try:
            detected = outside_items.detect(root, entries)
        except (OSError, ValueError, UnicodeError):
            self.outside_detected.pop(key, None)
            return {"state": "unavailable"}
        self.outside_detected[key] = detected
        return outside_items.counts(detected)

    def outside_status(self, key):
        with self.lock:
            if key not in self.repositories():
                raise ValueError("Unknown repository")
            detected = self.outside_detected.get(key)
            if detected is None:
                raise ValueError("Outside items have not been checked yet. Rescan this repo.")
            revision = self.outside_choices.revision()
            choices = self.outside_choices.for_repo(key, detected)
            refusals = self.inclusion_refusals(key, detected)
            kept = self.kept_items(key)
        # Sizes and Git status are measured only when the review page opens.
        return {"repo_id": key, "items": outside_items.review(detected, git_info, refusals),
                "choices": choices, "revision": revision, "kept": kept}

    def save_outside_choices(self, key, payload):
        if set(payload) != {"choices", "revision"}:
            raise ValueError("Invalid outside-item request")
        with self.lock:
            if key not in self.repositories():
                raise ValueError("Unknown repository")
            detected = self.outside_detected.get(key)
            if detected is None:
                raise FileExistsError("Outside items have not been checked yet. Rescan before saving.")
            known = {item["path"] for item in detected["links"] if item["category"] == "linked_folder"}
            outside_items.validate_repo(payload["choices"], known)
            chosen = {path for path, choice in payload["choices"]["linked_folders"].items() if choice == "include"}
            refused = self.inclusion_refusals(key, detected, chosen)
            if refused:
                path, reason = sorted(refused.items())[0]
                self.diagnostics.emit("outside_review", result="failed", reason=reason, repo_ref=diagnostic_ref(key))
                raise ValueError(outside_items.refusal_text(path, reason))
            self.outside_choices.save(key, payload["choices"], payload["revision"], known)
        self.diagnostics.emit("outside_review", result="saved", repo_ref=diagnostic_ref(key))
        return self.outside_status(key)

    def inclusion_guard(self):
        """Locations an included folder must never overlap."""
        return {"repositories": tuple(self.repositories().values()),
                "destinations": (self.backups, *(Path(path) for path in self.setup_record.get("previous_destinations", []))),
                "state": self.state_dir}

    def inclusion_refusals(self, key, detected, chosen=None):
        """Reason codes for linked folders that cannot be archived separately.

        With chosen paths, a later link to an already included folder is a duplicate.
        """
        root = self.repositories()[key]
        guard = self.inclusion_guard()
        refusals = {}
        seen = [] if chosen is not None else None
        for item in detected["links"]:
            if item["category"] != "linked_folder" or (chosen is not None and item["path"] not in chosen):
                continue
            real, reason = outside_items.inclusion_target(root / item["path"], seen=seen, **guard)
            if reason:
                refusals[item["path"]] = reason
            elif seen is not None:
                seen.append(real)
        return refusals

    def outside_plan(self, key, root, detected):
        """Included linked folders and checkouts as (group, name, source, item)."""
        choices = self.outside_choices.for_repo(key, detected)
        plan = [("linked", item["path"], Path(root) / item["path"], item)
                for item in outside_items.included_folders(detected, choices)]
        plan += [("checkouts", item["name"], Path(item["path"]), item)
                 for item in outside_items.included_checkouts(detected, choices, root)]
        return plan

    def outside_directory(self, key, group, name):
        return (self.layout.linked_directory(key, name) if group == "linked"
                else self.layout.checkout_directory(key, name))

    def outside_parts(self, key, current):
        """Archives that join the repo archive in one uploaded set."""
        parts = []
        for group, prefix, label in (("linked", LINKED, "Included folder "), ("checkouts", CHECKOUT, "Linked checkout ")):
            for name, entry in sorted(((current or {}).get(group) or {}).items()):
                parts.append((group, name, label + name, key + prefix + name, entry))
        return parts

    def kept_items(self, key):
        kept = (self.index.get(key) or {}).get("removed") or {}
        return [{"item": item, "kind": entry["kind"], "name": entry["name"], "reason": entry["reason"],
                 "removed_at": entry["removed_at"], "keep_until": entry.get("keep_until"),
                 "ref": diagnostic_ref(entry["archive"])} for item, entry in sorted(kept.items())]

    def included_state(self, key, root, current):
        """Compare included linked folders and checkouts with their saved archives using metadata only."""
        current = current or {}
        state = {"included": 0, "checkouts": 0, "pending": 0, "kept": len(current.get("removed") or {})}
        detected = self.outside_detected.get(key)
        if detected is None:
            return state
        try:
            plan = self.outside_plan(key, root, detected)
        except (OSError, ValueError):
            return state
        for group, name, source, _ in plan:
            state["included" if group == "linked" else "checkouts"] += 1
            entry = (current.get(group) or {}).get(name)
            try:
                real = source.resolve(strict=True)
                ok = bool(entry and entry.get("source") == str(real)
                          and Path(entry["archive"]).parent == self.outside_directory(key, group, name)
                          and Path(entry["archive"]).is_file()
                          and fingerprint(tree_entries(real)) == entry.get("signature"))
            except (OSError, ValueError, RuntimeError):
                ok = False
            state["pending"] += not ok
        # Saved items that are gone or no longer included move to the keep window at the next backup.
        planned = {(group, name) for group, name, _, _ in plan}
        state["pending"] += sum((group, name) not in planned for group in ("linked", "checkouts")
                                for name in (current.get(group) or {}))
        return state

    def archive_outside(self, key, root, entries, previous, run_id, observe, failures, deferred):
        """Archive included linked folders and checkouts beside the repo backup, each verified on its own.

        Returns the repo's linked, checkouts and removed maps. An item that cannot be
        archived keeps its last verified archive referenced and is reported for this
        repo. An item that is gone or no longer included moves to the keep window and
        rejoins the set if it returns.
        """
        previous = previous or {}
        saved = {group: dict(previous.get(group) or {}) for group in ("linked", "checkouts")}
        removed = dict(previous.get("removed") or {})
        try:
            detected = outside_items.detect(root, entries)
            plan = self.outside_plan(key, root, detected)
        except (OSError, ValueError, UnicodeError) as error:
            failures.append({"repo": root.name, "repo_id": key,
                             "error": "Items outside this folder could not be checked: " + str(error)})
            return {**saved, "removed": removed}
        result = {"linked": {}, "checkouts": {}}
        if plan:
            observe("included_folders")
        guard = self.inclusion_guard()
        seen = []
        for group, name, source, item in plan:
            label = ("Included folder " if group == "linked" else "Linked checkout ") + name
            kept_key = KEPT[group] + name
            earlier = saved[group].get(name) or removed.get(kept_key)
            real, refusal = outside_items.inclusion_target(source, seen=seen, **guard)
            if refusal:
                self.lifecycle.emit("included_folder_refused", key=key, run_id=run_id, reason=refusal, result="not_started")
                failures.append({"repo": root.name, "repo_id": key,
                                 "error": outside_items.refusal_text(name if group == "linked" else label, refusal)})
                if name in saved[group]:
                    result[group][name] = saved[group][name]
                continue
            seen.append(real)
            started = time.monotonic()
            try:
                destination = self.outside_directory(key, group, name)
                verified = None
                if (earlier and earlier.get("source") == str(real)
                        and Path(earlier["archive"]).parent == destination
                        and Path(earlier["archive"]).is_file()):
                    try:
                        verified = verify_current(real, earlier)
                    except SourceChanged:
                        raise
                    except (RuntimeError, tarfile.TarError):
                        verified = None  # Replace a damaged copy from the source; nothing is pruned first.
                if verified and (verified["state"] == "matched" or verified.get("ignored_finder_only") is True):
                    entry = {k: v for k, v in earlier.items() if k not in KEPT_FIELDS}
                    entry.update(signature=verified["signature"], content_signature=verified["archive_content_signature"])
                    result[group][name] = entry
                    removed.pop(kept_key, None)
                    self.lifecycle.emit("included_folder_archived", key=key, current=entry, result="reused")
                    continue

                def check_source():
                    self.registry.require_workspace(key, root)
                    if self.setup_record.get("destination"):
                        require_destination(self.setup_record["destination"])
                    LayoutTransaction.safe_target(self.backups, destination)
                    if group == "linked":
                        if os.readlink(source) != item["target"] or source.resolve() != real:
                            raise SourceChanged("An included folder's link changed during the backup")
                    elif source.resolve() != real or not (real / ".git").is_file():
                        raise SourceChanged("A linked checkout moved during the backup")
                created = snapshot(real, destination, self.state_dir / "staging", source_check=check_source)
                created.update(run_id=run_id, source=str(real))
                if group == "linked":
                    created["target"] = item["target"]
                result[group][name] = created
                removed.pop(kept_key, None)
                self.lifecycle.emit("included_folder_archived", key=key, current=created, result="created",
                                    bytes=created["archive_bytes"], duration_ms=(time.monotonic() - started) * 1000)
            except SourceChanged:
                deferred.append({"repo": root.name, "repo_id": key, "reason": "source_changed_during_verification"})
                self.lifecycle.emit("verification_deferred", key=key, run_id=run_id, stage="included_folders",
                                    reason="source_changed_during_verification", result="deferred")
                if name in saved[group]:
                    result[group][name] = saved[group][name]
            except Exception as error:
                self.lifecycle.emit("included_folder_failed", key=key, run_id=run_id, severity="error", result="failed",
                                    error_type=type(error).__name__, error_code=getattr(error, "errno", None))
                failures.append({"repo": root.name, "repo_id": key, "error": label + ": " + str(error)})
                if name in saved[group]:
                    result[group][name] = saved[group][name]
        # Following Git: a removed checkout or folder is not an error. Its last verified
        # archive stays in a keep window instead of being deleted immediately.
        now = datetime.now(timezone.utc)
        present = {"linked": {i["path"] for i in detected["links"] if i["category"] == "linked_folder"},
                   "checkouts": {i["name"] for i in detected["checkouts"] if i["state"] == "present"}}
        planned = {(group, name) for group, name, _, _ in plan}
        for group in ("linked", "checkouts"):
            for name, entry in saved[group].items():
                if (group, name) in planned:
                    continue
                if name not in present[group] and source_unreachable(entry.get("source")):
                    # Can't reach it right now (for example an unplugged drive): keep the last
                    # verified archive in the set, start no countdown, and report the problem.
                    result[group][name] = entry
                    label = ("Included folder " if group == "linked" else "Linked checkout ") + name
                    failures.append({"repo": root.name, "repo_id": key,
                                     "error": label + " is unavailable (is its drive connected?). "
                                              "Its last backup is kept."})
                    self.lifecycle.emit("outside_item_unavailable", key=key, run_id=run_id, result="kept")
                    continue
                reason = "excluded" if name in present[group] else "removed"
                removed[KEPT[group] + name] = {
                    **entry, "kind": group, "name": name, "reason": reason, "removed_at": now.isoformat(),
                    "keep_until": (now + KEEP_WINDOW).isoformat() if self.retention == "latest" else None}
                self.lifecycle.emit("outside_item_kept", key=key, run_id=run_id, reason=reason, result="kept")
        return {**result, "removed": removed}

    def delete_kept(self, key, item_key, reason):
        """Delete one kept item's managed archives. The caller holds the backup lock."""
        with self.lock:
            current = self.index.get(key) or {}
            entry = (current.get("removed") or {}).get(item_key)
            active = entry is not None and entry["name"] in (current.get(entry["kind"]) or {})
        if entry is None:
            return 0
        if active:
            raise ValueError("This item is backed up again; nothing was removed")
        directory = self.outside_directory(key, entry["kind"], entry["name"])
        managed = Path(entry["archive"]).parent == directory
        files = []
        if managed:
            if (directory.is_symlink() or (directory.exists() and directory.resolve() != directory)
                    or self.backups not in directory.parents):
                raise ValueError("Refusing to delete outside the managed snapshot folder")
            if directory.is_dir():
                files = [p for p in directory.iterdir() if ARCHIVE_NAME.fullmatch(p.name)
                         and p.is_file() and not p.is_symlink()]
        elif reason == "user_removed":
            raise ValueError("This kept backup is in a previous destination and was left in place")
        # A kept backup in a previous destination is left in place; only its record is dropped.
        for path in files:
            path.unlink()
        if files:
            try:
                directory.rmdir()
            except OSError:
                pass
        with self.lock:
            updated = self.index.get(key)
            if updated and item_key in (updated.get("removed") or {}):
                del updated["removed"][item_key]
                if not updated["removed"]:
                    updated.pop("removed")
                atomic_json(self.state_dir / "backups.json", self.index)
                atomic_json(self.backups / "index.json", self.index)
        self.lifecycle.emit("outside_item_deleted", key=key, reason=reason if managed else "previous_destination",
                            files=len(files), result="removed" if files else "kept")
        return len(files)

    def expire_kept(self, key):
        """Delete kept items whose 30-day window has passed. The caller holds the backup lock."""
        if self.retention != "latest":
            return
        with self.lock:
            kept = dict((self.index.get(key) or {}).get("removed") or {})
        now = time.time()
        for item_key, entry in kept.items():
            try:
                until = entry.get("keep_until")
                if until and datetime.fromisoformat(until).timestamp() <= now:
                    self.delete_kept(key, item_key, "keep_window_expired")
            except Exception as error:
                self.lifecycle.transition("retention_failed", key=key, severity="error", result="deferred",
                                          error_type=type(error).__name__)

    def remove_kept(self, key, payload):
        """Remove now: delete one kept item's archives at the user's request."""
        if (set(payload) != {"item", "ref"} or not isinstance(payload["item"], str)
                or not isinstance(payload["ref"], str)):
            raise ValueError("Invalid removal request")
        if key not in self.repositories():
            raise ValueError("Unknown repository")
        if not self.backup_lock.acquire(blocking=False):
            raise FileExistsError("A backup is running. Try again after it finishes.")
        try:
            with self.lock:
                entry = ((self.index.get(key) or {}).get("removed") or {}).get(payload["item"])
            if entry is None or diagnostic_ref(entry["archive"]) != payload["ref"]:
                raise FileExistsError("This item changed. Reopen this page before removing it.")
            self.delete_kept(key, payload["item"], "user_removed")
        finally:
            self.backup_lock.release()
        return self.outside_status(key)

    def automatic_tick(self):
        if not self.configured or self.setup_recovery_required:
            return
        self.diagnostics.heartbeat(repo_count=len(self.status["repos"]),
                                   scan_running=self.scan_lock.locked(),
                                   backup_running=self.backup_lock.locked())
        source = power_source()
        with self.lock:
            self.power = source
            rows = json.loads(json.dumps(self.status["repos"]))
            # Wall-clock cadence survives sleep/restarts; edit quiet periods use monotonic time.
            self.scheduler.last_periodic = time.monotonic() - max(0, time.time() - self.last_periodic_at)
            self.scheduler.periodic = {key: time.monotonic() - max(0, time.time() - timestamp)
                                       for key, timestamp in self.repo_periodic_at.items()}
            plan = self.scheduler.plan(self.settings, source, rows, time.monotonic(), self.repo_settings)
            plan_run_id = secrets.token_hex(12) if plan else None
            self.lifecycle.schedule(self.scheduler, self.settings, source, rows, time.monotonic(), self.repo_settings, plan, run_id=plan_run_id)
            policies = [self.repo_settings.get(row["id"], self.settings).get(source) for row in rows]
            self.status["schedule"] = {"paused": source == "unknown" or not any(
                policy and (policy["frequency_minutes"] or policy["after_edits"]) for policy in policies)}
        attempted = []
        if plan and self.backup(keys=plan["keys"], reason=plan["reason"], expected_power=source,
                                attempted_keys=attempted, run_id=plan_run_id):
            with self.lock:
                completed = dict(plan)
                completed["keys"] = attempted
                completed["periodic_keys"] = [key for key in plan.get("periodic_keys", []) if key in attempted]
                self.scheduler.completed(completed, rows, time.monotonic())
                if completed["periodic_keys"]:
                    self.record_periodic_clock(completed["periodic_keys"])

    def record_periodic_clock(self, keys=None):
        now = time.time()
        if keys is None:
            self.last_periodic_at = now
            self.repo_periodic_at = {}
        else:
            for key in keys:
                self.repo_periodic_at[key] = now
        atomic_json(self.state_dir / "schedule-clock.json",
                    {"last_periodic_at": self.last_periodic_at, "repos": self.repo_periodic_at})

    def cloud_for(self, key, current):
        """One upload state per repo: every archive in its set must be confirmed."""
        state = self.cloud_one(key, current)
        parts = [(label, self.cloud_one(upload_id, entry)) for _, _, label, upload_id, entry in self.outside_parts(key, current)]
        if not parts or all(part.get("state") == "uploaded" for _, part in parts):
            return state
        notes = {"error": "upload issue", "unknown": "upload status unavailable",
                 "pending": "upload not yet confirmed", "uploading": "uploading"}
        for wanted in ("error", "unknown", "pending", "uploading"):
            for label, part in [(None, state)] + parts:
                if part.get("state") == wanted:
                    combined = {k: v for k, v in part.items() if k not in ("percent", "progress_source")}
                    combined["archive"] = current["archive"]
                    if label is not None:
                        combined["detail"] = label + ": " + (part.get("detail") or notes[wanted])
                    return combined
        return {"state": "unknown", "archive": current["archive"]}

    def cloud_one(self, key, current):
        observed = self.cloud_states.get(key, {})
        if not current or observed.get("archive") != current["archive"]:
            return {"state": "unknown"}
        if age(observed.get("checked_at"), time.time()) > max(45, self.config.get("cloud_seconds", 5) * 6):
            self.lifecycle.transition("upload_stale", key=key, current=current, result="unknown", reason="observation_expired")
            return {"state": "unknown", "detail": "Upload status is outdated", "archive": current["archive"]}
        return observed

    def refresh_cloud(self):
        with self.lock:
            copies = json.loads(json.dumps(self.index))
        requests = [{"id": key, "path": value["archive"]} for key, value in copies.items()
                    if self.layout.contains(key, value['archive'])]
        targets = dict(copies)
        for key, value in copies.items():
            for group, name, _, upload_id, entry in self.outside_parts(key, value):
                try:
                    contained = Path(entry["archive"]).parent == self.outside_directory(key, group, name)
                except ValueError:
                    contained = False
                if contained:
                    requests.append({"id": upload_id, "path": entry["archive"]})
                    targets[upload_id] = entry
        helper = self.config.get("cloud_helper", str(Path(__file__).parent / "cloud-status"))
        try:
            result = subprocess.run([helper], input=json.dumps(requests), text=True,
                                    capture_output=True, timeout=15, check=True)
            raw = json.loads(result.stdout)
            if not isinstance(raw, dict):
                raise ValueError("Invalid upload-status response")
        except Exception as e:
            raw = {r["id"]: {"error": None, "probe_error": str(e)} for r in requests}
        checked = utc_now()
        observed = {}
        for request in requests:
            item = raw.get(request["id"], {})
            if not isinstance(item, dict):
                item = {"probe_error": "Invalid upload-status item"}
            state = cloud_status(item)
            if item.get("probe_error"):
                state = {"state": "unknown", "detail": "Upload-status helper unavailable"}
            self.lifecycle.transition("upload_observed", key=request["id"], current=targets[request["id"]],
                                      state=state["state"], percent=state.get("percent"),
                                      reason=state.get("reason", "helper_unavailable" if item.get("probe_error") else "macos_observation"),
                                      has_error=bool(item.get("error") or item.get("probe_error")),
                                      error_code=item.get("error_code") if type(item.get("error_code")) is int else None)
            observed[request["id"]] = {**state, "archive": request["path"], "checked_at": checked}
        with self.lock:
            self.cloud_states = observed
            for row in self.status["repos"]:
                row["cloud"] = self.cloud_for(row["id"], row.get("last_backup"))
            self.status["data_cloud"] = self.cloud_for("repohub-data", self.index.get("repohub-data"))
            self.status["cloud_checked_at"] = checked
            self.status["cloud_poll_seconds"] = self.config.get("cloud_seconds", 5)
            self.persist_status()
        if self.backup_lock.acquire(blocking=False):
            try:
                for key, current in copies.items():
                    if self.cloud_for(key, current).get("state") == "uploaded":
                        try:
                            self.retain_current(key, current)
                        except Exception as e:
                            self.lifecycle.transition("retention_failed", key=key, current=current,
                                                      severity="error", result="deferred", error_type=type(e).__name__)
                            print("Retention cleanup deferred:", key, str(e), flush=True)
                    self.expire_kept(key)
            finally:
                self.backup_lock.release()

    def retain_current(self, key, current):
        """Remove only managed superseded archives after verifying the retained copy."""
        if self.retention != "latest":
            self.lifecycle.transition("retention_decision", key=key, current=current, reason="keep_all", result="kept")
            return
        with self.lock:
            stored = self.index.get(key, {})
            if (stored.get("archive") != current["archive"]
                    or (stored.get("linked") or {}) != (current.get("linked") or {})
                    or (stored.get("checkouts") or {}) != (current.get("checkouts") or {})):
                raise ValueError("Refusing cleanup using a superseded upload observation")
        # The repo archive and each included folder or checkout archive form one retained set.
        groups = [(self.layout.directory(key), Path(current["archive"]), current["sha256"])]
        for group, name, _, _, entry in self.outside_parts(key, current):
            groups.append((self.outside_directory(key, group, name), Path(entry["archive"]), entry["sha256"]))
        obsolete = []
        for destination, retained, _ in groups:
            if (destination.is_symlink() or destination.resolve() != destination or self.backups not in destination.parents
                    or retained.parent != destination or retained.is_symlink()
                    or not ARCHIVE_NAME.fullmatch(retained.name)):
                raise ValueError("Refusing cleanup outside the managed snapshot folder")
            obsolete += [p for p in destination.iterdir() if p != retained
                         and ARCHIVE_NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()]
        if not obsolete:
            self.lifecycle.transition("retention_decision", key=key, current=current, reason="no_superseded_archives", result="kept")
            return
        # Always keep the previous copy until macOS confirms the replacement reached the cloud.
        # This is not configurable: an older or hand-written config must never lose the only
        # uploaded copy. The require_upload_before_prune key is still accepted but ignored.
        if self.cloud_for(key, current).get("state") != "uploaded":
            self.lifecycle.transition("retention_decision", key=key, current=current, reason="awaiting_upload", result="kept")
            return
        for _, retained, digest in groups:
            if sha256(retained) != digest:
                raise RuntimeError("Current archive failed verification; older backups were kept")
        self.lifecycle.emit("retention_verified", key=key, current=current, files=len(obsolete), result="verified")
        for path in obsolete:
            self.lifecycle.emit("prune_started", key=key, current=current, previous_archive_ref=diagnostic_ref(str(path)))
            path.unlink()
            self.lifecycle.emit("prune_finished", key=key, current=current, previous_archive_ref=diagnostic_ref(str(path)), result="removed")

    def backup(self, keys=None, reason="manual", expected_power=None, attempted_keys=None, run_id=None, _lock_held=False):
        if not self.configured or self.setup_recovery_required:
            raise ValueError('Finish setup or recover its interrupted save before starting backups')
        run_id = run_id or secrets.token_hex(12)
        started = time.monotonic()
        if expected_power is not None and power_source() != expected_power:
            self.lifecycle.emit("backup_deferred", run_id=run_id, reason="power_changed", result="not_started")
            return False
        if not _lock_held and not self.backup_lock.acquire(blocking=False):
            self.lifecycle.emit("backup_deferred", run_id=run_id, reason="backup_busy", result="not_started")
            return False
        # Select sources under the same lock as configuration saves. Otherwise
        # a removed source could be archived after the new selection was saved.
        try:
            repositories = self.repositories()
            if keys is not None and (not isinstance(keys, (list, tuple, set)) or any(not isinstance(key, str) or key not in repositories for key in keys)):
                raise ValueError("Backup selection must contain current workspace IDs")
        except BaseException:
            self.backup_lock.release()
            raise
        if keys is not None and not keys:
            self.backup_lock.release()
            return False
        failures = []
        deferred = []
        outcome = "complete"
        self.lifecycle.emit("backup_started", run_id=run_id, previous_run_id=self.status.get("backup", {}).get("run_id") or self.previous_backup_run,
                            reason=reason, mode="all" if keys is None else "selected")
        try:
            with self.lock:
                self.status["backup"] = {"running": True, "started_at": utc_now(), "current_repo": None, "current_repo_id": None, "reason": reason, "run_id": run_id}
                self.persist_status()
            if self.setup_record.get('destination'):
                require_destination(self.setup_record['destination'])
            if not self.backups.parent.is_dir():
                raise FileNotFoundError(2, "Backup destination unavailable")
            backup_sources = {key: root for key, root in repositories.items() if keys is None or key in keys}
            backup_sources["repohub-data"] = self.data_dir
            for key, root in backup_sources.items():
                if expected_power is not None and power_source() != expected_power:
                    outcome = "failed_power_paused" if failures else "power_paused"
                    self.lifecycle.emit("backup_paused", run_id=run_id, reason="power_changed", result="partial")
                    break  # Finish an in-flight archive, then respect the new power source.

                if attempted_keys is not None and key != "repohub-data":
                    attempted_keys.append(key)
                with self.lock:
                    self.status["backup"]["current_repo"] = root.name
                    self.status["backup"]["current_repo_id"] = key
                    self.persist_status()
                current_archive = None
                stage = "source_inspection"
                repo_started = time.monotonic()
                self.lifecycle.emit("repo_backup_started", key=key, run_id=run_id)
                def observe(value):
                    nonlocal stage
                    stage = value
                    self.lifecycle.emit("archive_stage", key=key, run_id=run_id, stage=value)
                try:
                    destination = self.setup.allocate(key, root)
                    require_source(root, canonical_only=True)
                    if key != "repohub-data":self.registry.require_workspace(key, root)
                    entries = tree_entries(root)
                    signature = fingerprint(entries)
                    with self.lock:
                        previous = self.index.get(key)
                    outside = {}
                    if key != "repohub-data":
                        counted = (len(failures), len(deferred))
                        outside = self.archive_outside(key, root, entries, previous, run_id, observe, failures, deferred)
                        if len(failures) > counted[0]:
                            outcome = "failed"
                        elif len(deferred) > counted[1] and outcome == "complete":
                            outcome = "deferred"
                        stage = "source_inspection"
                    current_archive = (previous or {}).get("archive")
                    verified = None
                    if previous and self.layout.contains(key, previous['archive']) and Path(previous["archive"]).is_file():
                        try:
                            observe("existing_verification")
                            verified = verify_current(root, previous)
                        except SourceChanged:
                            raise  # Handled as a typed deferral outside the archive-repair path.
                        except OSError as error:
                            # A cloud placeholder/read failure is not evidence of corruption.
                            # Keep the current backup and let the normal retry policy try again.
                            try:
                                flags = Path(previous["archive"]).stat().st_flags
                                dataless = bool(flags & getattr(stat, "SF_DATALESS", 0x40000000))
                            except (OSError, AttributeError):
                                dataless = None
                            self.lifecycle.emit("verification_deferred", key=key, run_id=run_id,
                                                previous_archive_ref=diagnostic_ref(previous["archive"]),
                                                stage="existing_verification", reason="verification_io_unavailable",
                                                mode="posix", error_code=error.errno, error_type=type(error).__name__,
                                                archive_dataless=dataless, result="deferred")
                            raise
                        except (RuntimeError, tarfile.TarError) as error:
                            self.lifecycle.emit("archive_repair_needed", key=key, run_id=run_id,
                                                previous_archive_ref=diagnostic_ref(previous["archive"]), error_type=type(error).__name__)
                            pass  # Replace a corrupt copy from the intact source; do not prune first.
                    if key != "repohub-data":self.registry.require_workspace(key, root)
                    if (verified and self.layout.contains(key, previous['archive'])
                            and (verified["state"] == "matched" or verified.get("ignored_finder_only") is True)):
                        with self.lock:
                            self.verifications[key] = verified
                            previous["content_signature"] = verified["archive_content_signature"]
                            set_outside(previous, outside)
                            atomic_json_if_changed(self.state_dir / "backups.json", self.index)
                        self.lifecycle.emit("archive_reused", key=key, run_id=run_id,
                                            archive_ref=diagnostic_ref(previous["archive"]),
                                            reason="finder_only" if verified.get("ignored_finder_only") else "contents_match")
                        observe("publication_recovery")
                        # Finish an interrupted publication/cleanup without making another copy.
                        atomic_json_if_changed(self.backups / "index.json", self.index)
                        self.retain_current(key, previous)
                        self.expire_kept(key)
                        self.lifecycle.emit("repo_backup_finished", key=key, run_id=run_id, result="reused",
                                            archive_ref=diagnostic_ref(previous["archive"]), duration_ms=(time.monotonic()-repo_started)*1000)
                        continue
                    def check_context():
                        if key != 'repohub-data':
                            self.registry.require_workspace(key, root)
                        if self.setup_record.get('destination'):
                            require_destination(self.setup_record['destination'])
                        LayoutTransaction.safe_target(self.backups, destination)
                    result = snapshot(root, destination, self.state_dir / "staging", expected=signature,
                                      observe=observe, source_check=check_context)
                    current_archive = result["archive"]
                    self.lifecycle.emit("archive_verified", key=key, run_id=run_id, archive_ref=diagnostic_ref(current_archive),
                                        backup_hash_ref=diagnostic_ref(result["sha256"]), result="verified")
                    result["run_id"] = run_id
                    result["name"] = root.name
                    set_outside(result, outside)
                    observe("index_publication")
                    with self.lock:
                        self.index[key] = result
                        atomic_json(self.state_dir / "backups.json", self.index)
                        atomic_json(self.backups / "index.json", self.index)
                        if key == "repohub-data":
                            self.status["data_backup"] = result
                        self.verifications[key] = {"state": "matched", "checked_at": utc_now(),
                                                   "signature": result["signature"], "archive": result["archive"],
                                                   "archive_stamp": archive_stamp(result["archive"])}
                    observe("retention")
                    self.retain_current(key, result)
                    self.expire_kept(key)
                    self.lifecycle.emit("repo_backup_finished", key=key, current=result, result="created",
                                        bytes=result["archive_bytes"], duration_ms=(time.monotonic()-repo_started)*1000)
                except SourceChanged:
                    # A changing source cannot establish a consistent comparison.
                    # Preserve the archive and the attempt history, without making
                    # later successful scans inherit a permanent backup error.
                    if outcome == "complete":
                        outcome = "deferred"
                    deferred.append({"repo": root.name, "repo_id": key,
                                     "reason": "source_changed_during_verification"})
                    verification = {"state": "changing", "checked_at": utc_now(),
                                    "reason": "source_changed_during_verification"}
                    with self.lock:
                        self.verifications[key] = verification
                        for row in self.status["repos"]:
                            if row["id"] == key:
                                row["verification"] = dict(verification)
                                row["needs_backup"] = True
                    self.lifecycle.emit("verification_deferred", key=key, run_id=run_id,
                                        stage=stage, archive_ref=diagnostic_ref(current_archive),
                                        reason="source_changed_during_verification", result="deferred")
                except Exception as e:
                    outcome = "failed"
                    self.lifecycle.emit("repo_backup_failed", key=key, run_id=run_id, stage=stage, archive_ref=diagnostic_ref(current_archive),
                                        severity="error", result="failed", error_type=type(e).__name__,
                                        error_code=getattr(e, "errno", None), duration_ms=(time.monotonic()-repo_started)*1000)
                    failure = {"repo": root.name, "repo_id": key, "error": str(e)}
                    if isinstance(e, OSError):
                        failure["access"] = access_failure(e, "destination_write" if stage in {"archive_transfer", "destination_verification", "index_publication", "publication_recovery"} else "verification_read" if stage == "existing_verification" else "source_read")
                        failure["error"] = failure["access"]["detail"]
                    failures.append(failure)
            with self.lock:
                note = ("Last backup attempt waited for changing files; previous archives were kept. "
                        "macOS manages iCloud upload." if deferred else
                        "Archives verified locally. macOS manages iCloud upload.")
                self.status["backup"] = {"running": False, "finished_at": utc_now(), "run_id": run_id,
                                         "errors": failures, "deferred": deferred,
                                         "note": note}
                self.persist_status()
        except Exception as e:
            outcome = "failed"
            self.lifecycle.emit("backup_failed", run_id=run_id, severity="error", error_type=type(e).__name__)
            with self.lock:
                self.status["backup"] = {"running": False, "finished_at": utc_now(), "run_id": run_id, "errors": [{"error": str(e)}]}
                self.persist_status()
        finally:
            self.lifecycle.emit("backup_finished", run_id=run_id, result=outcome, duration_ms=(time.monotonic()-started)*1000)
            self.backup_lock.release()
            self.scan()
            if reason == "manual":
                with self.lock:
                    self.scheduler.manual_completed(time.monotonic(), keys=keys)
                    self.record_periodic_clock(keys)
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
            if path.startswith("/api/repo-settings/"):
                return self.send(self.hub.repo_settings_status(path.removeprefix("/api/repo-settings/")))
            if path.startswith("/api/outside/"):
                return self.send(self.hub.outside_status(path.removeprefix("/api/outside/")))
            if path == "/api/readiness":
                return self.send(self.hub.readiness_status())
            if path == "/api/workspaces":
                return self.send(self.hub.workspace_status())
            if path == '/api/setup':
                return self.send(self.hub.setup.status())
            if path == '/api/setup/operation':
                return self.send(self.hub.setup.snapshot())
            if path == '/api/discovery':
                return self.send(self.hub.discovery.status())
            if path == "/api/settings":
                return self.send(self.hub.settings_status())
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
                      "/view-client.js": "view-client.js", "/notes.html": "notes.html",
                      "/readiness.js": "readiness.js", "/readiness.css": "readiness.css",
                      "/workspace-setup.js": "workspace-setup.js", "/workspace-setup.css": "workspace-setup.css",
                      "/menu.html": "menu.html", "/menu.css": "menu.css", "/menu.js": "menu.js",
                      "/menu-appearance.js": "menu-appearance.js",
                      "/update-channels.js": "update-channels.js",
                      "/outside-items.js": "outside-items.js",
                      "/setup.html": "setup.html", "/setup.js": "setup.js", "/setup.css": "setup.css",
                      "/report.css": "report.css", "/report-preview.js": "report-preview.js", "/repo-status.js": "repo-status.js", "/diagnostics-client.js": "diagnostics-client.js"}
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
            if not isinstance(payload, dict):
                raise ValueError("Request must be an object")
            path = unquote(urlparse(self.path).path)
            if path in {'/api/setup/review', '/api/setup/apply', '/api/setup/continue',
                        '/api/discovery/start', '/api/discovery/cancel'}:
                try:
                    if path == '/api/setup/continue':
                        return self.send(self.hub.setup.continue_current(payload))
                    if path.startswith('/api/setup/'):
                        return self.send(self.hub.setup.start(path.rsplit('/', 1)[1], payload), 202)
                    fields = set(payload)
                    if path.endswith('/start'):
                        valid_fields = fields in ({'parent'}, {'parent', 'destination'})
                    else:
                        valid_fields = fields == {'id'}
                    if not valid_fields:
                        raise ValueError('Invalid discovery request')
                    destination = payload.get('destination', '')
                    if not isinstance(destination, str) or (destination and not Path(destination).is_absolute()):
                        raise ValueError('Invalid draft destination')
                    value = (self.hub.discovery.start(payload['parent'], [destination] if destination else ()) if path.endswith('/start')
                             else self.hub.discovery.cancel(payload['id']))
                    return self.send(value, 202)
                except FileExistsError as error:
                    return self.send({'error': str(error)}, 409)
            if path.startswith("/api/outside/") and path.endswith("/remove"):
                try:
                    return self.send(self.hub.remove_kept(
                        path.removeprefix("/api/outside/").removesuffix("/remove"), payload))
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
            if path.startswith("/api/outside/"):
                try:
                    return self.send(self.hub.save_outside_choices(path.removeprefix("/api/outside/"), payload))
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
            if path.startswith("/api/repo-settings/"):
                try:
                    return self.send(self.hub.save_repo_settings(path.removeprefix("/api/repo-settings/"), payload))
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
            if path == "/api/settings":
                try:
                    return self.send(self.hub.save_settings(payload))
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
            if path == "/api/readiness/check":
                if payload:raise ValueError("Unknown access-check field")
                try:return self.send(self.hub.start_readiness())
                except FileExistsError as error:return self.send({"error":str(error)},409)
            if path == "/api/diagnostics/presentation":
                try:
                    return self.send(self.hub.evidence.presentation(payload))
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
            if path == "/api/diagnostics/menu-bar":
                try:
                    return self.send(self.hub.evidence.menu_bar_presentation(payload))
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
            if path == "/api/workspaces/preview":
                try:
                    return self.send(self.hub.preview_workspaces(payload))
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
            if path == "/api/workspaces":
                try:
                    return self.send(self.hub.save_workspaces(payload))
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
            if path == "/api/reports/connection":
                if payload: raise ValueError("Unknown connection field")
                return self.send(connection_status())
            if path == "/api/reports/send":
                return self.send(send_report(self.hub.state_dir, payload, logger=self.hub.diagnostics))
            if path == "/api/reports/draft":
                if set(payload) != {"report_id"}: raise ValueError("Invalid draft request")
                case = case_path(self.hub.state_dir, payload["report_id"])
                return self.send({"draft":read_private(case / "draft.json"), "delivery":delivery_status(self.hub.state_dir, payload["report_id"])})
            if path == "/api/reports/list":
                if payload: raise ValueError("Unknown report field")
                parent = self.hub.state_dir / "reports"
                if parent.is_symlink(): raise ValueError("Unsafe report directory")
                cases = sorted(parent.glob("*/draft.json"), key=lambda p:p.stat().st_mtime, reverse=True)[:25]
                rows = []
                for file in cases:
                    try:
                        case = case_path(self.hub.state_dir, file.parent.name)
                        draft = read_private(case / "draft.json")
                        rows.append({"report_id":draft["report_id"], "title":draft["title"], "type":draft["type"], **delivery_status(self.hub.state_dir, draft["report_id"])})
                    except (OSError, ValueError, KeyError): continue
                return self.send({"reports":rows})
            if path == "/api/reports/preview":
                return self.send(preview_report(self.hub.state_dir, self.hub.diagnostics.directory, payload), 201)
            if path in {"/api/actions/backup", "/api/actions/scan"}:
                try:
                    result = self.hub.request_selected_action(path.rsplit("/", 1)[1], payload)
                except FileExistsError as error:
                    return self.send({"error": str(error)}, 409)
                except OSError as error:
                    return self.send({"error": access_failure(error, "source_read")["detail"]}, 400)
                return self.send(result, 202)
            if path == "/api/backup":
                threading.Thread(target=self.hub.backup, daemon=True).start()
                return self.send({"accepted": True}, 202)
            if path == "/api/retry-check":
                if set(payload) != {"repo_id"}: raise ValueError("Invalid retry fields")
                try:
                    self.hub.retry_check(payload["repo_id"])
                except FileExistsError as e:
                    return self.send({"error": str(e)}, 409)
                return self.send({"accepted": True}, 202)
            if path == "/api/scan":
                threading.Thread(target=self.hub.scan, kwargs={"force": True}, daemon=True).start()
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


class ThreadingHTTPServer(StandardThreadingHTTPServer):
    """The local helper needs no hostname discovery or reverse DNS."""
    def server_bind(self):
        if self.server_address[0] != "127.0.0.1":
            raise ValueError("Loopback address required")
        # HTTPServer.server_bind calls socket.getfqdn, which can block on the
        # host's resolver before listen(). Keep TCP binding and explicit facts.
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]



def port_conflict(hub, port, own):
    """Describe whatever holds the helper port without changing it."""
    reason, other = "port_in_use", None
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://127.0.0.1:%d/api/status" % port, timeout=2) as response:
            status = json.load(response)
        if isinstance(status, dict) and isinstance(status.get("repos"), list):
            reason = "another_copy_running"
            release = status.get("application_release")
            if isinstance(release, dict) and isinstance(release.get("build"), str):
                other = release["build"][:16]
    except (OSError, ValueError):
        pass
    record = {"reason": reason, "port": port, "own_build": (own or {}).get("build"),
              "other_build": other, "detected_at": utc_now()}
    atomic_json(hub.state_dir / "helper-conflict.json", record)
    hub.diagnostics.emit("helper_conflict", result="failed", reason=reason, severity="error")
    return record


def watch_parent(hub, parent, getppid=os.getppid, interval=2.0, stop=None):
    """A bundled helper belongs to the app that started it; never outlive it holding the port."""
    stop = stop or (lambda: os._exit(0))
    while getppid() == parent:
        time.sleep(interval)
    hub.backup_lock.acquire()  # An in-flight archive publication finishes first.
    hub.diagnostics.emit("helper_parent_exited", result="complete", reason="parent_exited")
    stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--backup-once", action="store_true")
    parser.add_argument("--bundled", action="store_true")
    args = parser.parse_args()
    config = load_json(args.config, None)
    if not config:
        raise SystemExit("Missing configuration")
    config.pop('_setup_test_cloud_root', None)
    if args.bundled:
        # The signed native entry point verifies these resources before exec.
        # Override stale external runtime paths in memory, never in saved settings.
        config["cloud_helper"] = str(Path(__file__).parent / "cloud-status")
        release = load_json(Path(__file__).parent.parent / 'release.json', {})
        if str(release.get('bundle_id', '')).startswith('com.leogoldberg.repohub.test.'):
            config['_setup_test_cloud_root'] = str(Path(config['state_dir']).parent / 'cloud')
    hub = Hub(config)
    if args.bundled:
        release = load_json(Path(__file__).parent.parent / "release.json", {})
        hub.application_release = {key: release[key] for key in
                                   ("source_revision", "build", "bundle_id")}
    if args.backup_once:
        hub.backup()
        return
    if args.bundled:
        def stop_for_update(signum, frame):
            # A newly started backup can race the native idle check. Wait for
            # its actual lock instead of terminating an archive publication.
            hub.backup_lock.acquire()
            hub.diagnostics.emit("update_checkpoint", result="complete", reason="helper_stopped")
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, stop_for_update)
    port = config.get("port", 8767)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        # Another RepoHub copy (or another program) owns the port. Record it for the
        # app and the update watchdog instead of exiting with an unexplained traceback.
        conflict = port_conflict(hub, port, getattr(hub, "application_release", None))
        print("Helper port %d is in use (%s); this helper is exiting." % (port, conflict["reason"]), flush=True)
        raise SystemExit(75)
    if args.bundled:
        (hub.state_dir / "helper-conflict.json").unlink(missing_ok=True)
        parent = os.getppid()
        if parent != 1:
            threading.Thread(target=watch_parent, args=(hub, parent), daemon=True).start()
    server.hub = hub
    def scans():
        while True:
            time.sleep(config.get("scan_seconds", 30))
            try:
                hub.scan(deep=not hub.public_status()["backup"].get("running"))
            except Exception as e:
                hub.diagnostics.emit("runtime_error", stage="scan", error_type=type(e).__name__)
                print("Scan failed:", e, flush=True)
    def backups():
        while True:
            try:
                hub.automatic_tick()
            except Exception as e:
                hub.diagnostics.emit("runtime_error", stage="scheduler", error_type=type(e).__name__)
                print("Backup scheduler failed:", e, flush=True)
            time.sleep(15)
    threading.Thread(target=scans, daemon=True).start()
    threading.Thread(target=backups, daemon=True).start()
    def cloud_checks():
        while True:
            started = time.monotonic()
            try:
                hub.refresh_cloud()
            except Exception as e:
                hub.diagnostics.emit("runtime_error", stage="cloud", error_type=type(e).__name__)
                print("Upload-status check failed:", e, flush=True)
            time.sleep(max(1, config.get("cloud_seconds", 5) - (time.monotonic() - started)))
    threading.Thread(target=cloud_checks, daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
