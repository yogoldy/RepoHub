"""Bounded local diagnostics. Failure to write a log must never stop a backup."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time

MANAGED = re.compile(r"events-\d{20}-[0-9a-f]{12}-\d{6}\.jsonl$")
SCHEMA_VERSION = 1
MAX_RECORD = 8192
# Callers may supply only diagnostic facts, not opaque payloads or exception prose.
FIELDS = frozenset("report_ref archive_dataless previous_run_id frequency_minutes after_edits edit_delay_minutes error_code previous_archive_ref copying verification_archive_ref cloud_archive_ref build_id run_id scan_id repo_ref archive_ref observation_id client_id surface native policy_version stage result reason mode state has_error has_backup backup_hash_ref ignored_finder_only backup_required edit_signature previous_signature source_signature backup_signature content_signature archive_content_signature verification_state verification_checked_at duration_ms files bytes counts samples cached needs_backup metadata_changed fresh scan_running backup_running repo_count uptime_seconds gap_seconds dropped_events error_type display_label phase percent previous_scan_id".split())
SAMPLE_FIELDS = {"path_ref", "category", "change", "known_file"}
COUNTS = {"finder_metadata", "git_data", "repo_files"}


def diagnostic_ref(value):
    import hashlib
    return hashlib.sha256(str(value).encode()).hexdigest()[:16] if value else None


def _fields(values):
    if set(values) - FIELDS:
        raise ValueError("Unknown diagnostic field")
    result = {}
    for key, value in values.items():
        if value is None or type(value) in (bool, int):
            result[key] = value
        elif type(value) is float and math.isfinite(value):
            result[key] = round(value, 3)
        elif isinstance(value, str) and len(value) <= 160:
            result[key] = value
        elif key == "counts" and isinstance(value, dict) and set(value) <= COUNTS:
            if any(type(v) is not int or v < 0 for v in value.values()):
                raise ValueError("Invalid diagnostic counts")
            result[key] = value
        elif key == "samples" and isinstance(value, list) and len(value) <= 8:
            if any(not isinstance(v, dict) or set(v) - SAMPLE_FIELDS
                   or any(not isinstance(s, str) or len(s) > 64 for s in v.values()) for v in value):
                raise ValueError("Invalid diagnostic samples")
            result[key] = value
        else:
            raise ValueError("Unsupported diagnostic value")
    return result


class DiagnosticLog:
    def __init__(self, directory, *, file_bytes=10 * 1024 * 1024,
                 total_bytes=100 * 1024 * 1024, retention_seconds=7 * 86400,
                 clock=time.time, monotonic=time.monotonic):
        if not (0 < file_bytes <= total_bytes and retention_seconds > 0):
            raise ValueError("Invalid diagnostic limits")
        self.directory = Path(directory)
        self.file_bytes, self.total_bytes, self.retention_seconds = file_bytes, total_bytes, retention_seconds
        self.clock, self.monotonic = clock, monotonic
        self.session_id = secrets.token_hex(6)
        self.lock = threading.RLock()
        self.active = None
        self.sequence = 0
        self.written = self.failed = self.dropped = 0
        self.last_error = None
        self.started = monotonic()
        self.last_heartbeat = None
        self.last_wall = None

    def _directory(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or self.directory.is_symlink():
            raise OSError("Unsafe diagnostic directory")
        os.chmod(self.directory, 0o700)

    def _files(self):
        result = []
        for path in self.directory.iterdir():
            if not MANAGED.fullmatch(path.name):
                continue
            info = path.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                result.append((path, info))
        return sorted(result, key=lambda item: (item[1].st_mtime_ns, item[0].name))

    def _prune(self, now, pending):
        files = self._files()
        total = sum(info.st_size for _, info in files)
        for path, info in files:
            if info.st_mtime < now - self.retention_seconds or total + pending > self.total_bytes:
                path.unlink()
                total -= info.st_size
                if path == self.active:
                    self.active = None

    def emit(self, event, **values):
        with self.lock:
            try:
                if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", event):
                    raise ValueError("Invalid diagnostic event")
                severity = values.pop("severity", "error" if event == "runtime_error" else "warning" if event == "runtime_gap" else "info")
                if severity not in {"info", "warning", "error"}:
                    raise ValueError("Invalid diagnostic severity")
                now = self.clock()
                record = {"schema_version": SCHEMA_VERSION, "app_version": "0.1.0",
                          "utc": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                          "session_id": self.session_id, "event": event, "severity": severity, **_fields(values)}
                if self.dropped:
                    record["dropped_events"] = self.dropped
                body = (json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
                if len(body) > min(MAX_RECORD, self.file_bytes):
                    raise ValueError("Oversized diagnostic record")
                self._directory()
                self._prune(now, len(body))
                if self.active is not None:
                    info = self.active.lstat()
                    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                            or info.st_size + len(body) > self.file_bytes):
                        self.active = None
                flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
                if self.active is None:
                    self.sequence += 1
                    self.active = self.directory / f"events-{int(now * 1e9):020d}-{self.session_id}-{self.sequence:06d}.jsonl"
                    flags |= os.O_CREAT | os.O_EXCL
                fd = os.open(self.active, flags, 0o600)
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise OSError("Unsafe diagnostic file")
                    os.fchmod(fd, 0o600)
                    pending = memoryview(body)
                    while pending:
                        written = os.write(fd, pending)
                        if written <= 0:
                            raise OSError("Diagnostic write did not advance")
                        pending = pending[written:]
                finally:
                    os.close(fd)
                self.written += 1
                self.dropped = 0
                self.last_error = None
                return True
            except (OSError, ValueError, TypeError, OverflowError) as error:
                self.failed += 1
                self.dropped += 1
                self.last_error = type(error).__name__
                self.active = None  # A partial last line is left intact; next write starts a new file.
                return False

    def heartbeat(self, **facts):
        with self.lock:
            now, wall = self.monotonic(), self.clock()
            if self.last_wall is not None and wall - self.last_wall > 120:
                self.emit("runtime_gap", gap_seconds=wall - self.last_wall, result="unobserved_interval")
            self.last_wall = wall
            if self.last_heartbeat is not None and now - self.last_heartbeat < 60:
                return
            self.last_heartbeat = now
            self.emit("heartbeat", uptime_seconds=max(0, now - self.started), **facts)

    def status(self):
        with self.lock:
            return {"schema_version": SCHEMA_VERSION, "session_id": self.session_id,
                    "state": "unavailable" if self.last_error else "recording",
                    "written_events": self.written, "failed_events": self.failed,
                    "error_type": self.last_error}


def read_events(directory):
    """Local analysis only. Ignore links, oversized and interrupted final records."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        return
    for path in sorted(directory.iterdir()):
        if not MANAGED.fullmatch(path.name):
            continue
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    continue
                while True:
                    line = source.readline(MAX_RECORD + 1)
                    if not line:
                        break
                    if len(line) > MAX_RECORD or not line.endswith(b"\n"):
                        # Drain the rest of a malformed line without unbounded allocation.
                        while line and not line.endswith(b"\n"):
                            line = source.readline(MAX_RECORD + 1)
                        continue
                    try:
                        value = json.loads(line)
                        if (isinstance(value, dict) and value.get("schema_version") == SCHEMA_VERSION
                                and isinstance(value.get("event"), str) and isinstance(value.get("utc"), str)
                                and isinstance(value.get("session_id"), str)):
                            yield value
                    except (ValueError, UnicodeDecodeError):
                        pass
        except OSError:
            continue
