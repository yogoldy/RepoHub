"""Bounded local Git discovery. Results are candidates, never active workspaces."""
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time

from workspace_registry import source_identity


def git_candidate(path, git):
    path = Path(path)
    marker = path / '.git'
    if not marker.exists() and not marker.is_symlink():
        return None
    result = {'path': str(path), 'name': path.name, 'selectable': False, 'reason': 'invalid_git'}
    if marker.is_symlink():
        return {**result, 'reason': 'external_git_storage'}
    metadata = marker
    if marker.is_file():
        if marker.stat().st_size > 4096:
            return result
        line = marker.read_text().strip()
        if not line.startswith('gitdir: ') or '\n' in line:
            return result
        metadata = (path / line[8:]).resolve()
        if path not in metadata.parents:
            return {**result, 'reason': 'external_git_storage'}
    if not metadata.is_dir():
        return result
    # External worktree/common/alternate object stores are outside snapshot scope.
    if any((metadata / name).is_symlink() for name in (
            'objects', 'objects/pack', 'objects/info', 'refs', 'refs/heads',
            'refs/tags', 'refs/remotes', 'HEAD', 'config', 'packed-refs')):
        return {**result, 'reason': 'external_git_storage'}
    if (metadata / 'commondir').exists() or (metadata / 'objects/info/alternates').exists():
        return {**result, 'reason': 'external_git_storage'}
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_CONFIG_SYSTEM=os.devnull, GIT_TERMINAL_PROMPT='0')
    process = subprocess.run([git, '--no-optional-locks', '--git-dir', str(metadata),
                              'rev-parse', '--is-bare-repository'], env=environment,
                             capture_output=True, text=True, timeout=3)
    if process.returncode != 0 or process.stdout.strip() != 'false':
        return result
    return {**result, 'selectable': True, 'reason': 'git_repository'}


class GitDiscovery:
    def __init__(self, protected, *, max_directories=50000, max_depth=64, max_results=2000, seconds=120,
                 diagnostics=None):
        self.protected = tuple(Path(path).resolve() for path in protected)
        self.limits = (max_directories, max_depth, max_results, seconds)
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.job = None
        self.diagnostics = diagnostics

    def status(self):
        with self.lock:
            if self.job is None:
                return {'state': 'idle'}
            return {**self.job, 'results': [dict(row) for row in self.job['results']],
                    'warnings': [dict(row) for row in self.job['warnings']]}

    def start(self, raw, exclude=()):
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise ValueError('Choose a parent folder')
        parent = Path(raw).resolve(strict=True)
        protected = (*self.protected, *(Path(item).resolve() for item in exclude))
        if any(parent == item or item in parent.parents for item in protected):
            raise ValueError('Choose a source parent outside backups and app state')
        identity = source_identity(parent)
        with self.lock:
            if self.job and self.job['state'] == 'running':
                raise FileExistsError('Git discovery is already running')
            self.cancelled.clear()
            self.job = {'id': secrets.token_hex(12), 'state': 'running', 'parent': str(parent),
                        'visited': 0, 'results': [], 'warnings': [], 'incomplete': False}
            snapshot = self.status()
            threading.Thread(target=self.run, args=(parent, identity, protected), daemon=True).start()
            return snapshot

    def cancel(self, job_id):
        with self.lock:
            if not self.job or self.job['id'] != job_id:
                raise ValueError('Unknown discovery request')
            self.cancelled.set()
            return self.status()

    def warning(self, path, reason):
        with self.lock:
            self.job['incomplete'] = True
            if len(self.job['warnings']) < 100:
                self.job['warnings'].append({'path': str(path), 'reason': reason})

    def run(self, parent, identity, protected):
        git = shutil.which('git')
        started = time.monotonic()
        maximum, depth_limit, result_limit, deadline = self.limits
        stack = [(parent, 0)]
        final = 'complete'
        try:
            if not git:
                raise FileNotFoundError('Git is unavailable. Install Apple command line tools to scan Git repos.')
            while stack:
                if self.cancelled.is_set():
                    final = 'cancelled'; break
                directory, depth = stack.pop()
                with self.lock:
                    visited, count = self.job['visited'], len(self.job['results'])
                if visited >= maximum or count >= result_limit or time.monotonic() - started >= deadline:
                    self.warning(directory, 'traversal_limit'); break
                if directory.is_symlink():
                    self.warning(directory, 'symlink_skipped'); continue
                if any(directory == item or item in directory.parents for item in protected):
                    continue
                try:
                    with self.lock:
                        self.job['visited'] += 1
                    candidate = git_candidate(directory, git)
                    if candidate:
                        with self.lock:
                            self.job['results'].append(candidate)
                    with os.scandir(directory) as entries:
                        children = sorted((Path(entry.path) for entry in entries
                                           if entry.name != '.git' and not entry.name.startswith('.repohub')
                                           and entry.is_dir(follow_symlinks=False)), reverse=True)
                    if depth >= depth_limit and children:
                        self.warning(directory, 'depth_limit')
                    else:
                        stack.extend((child, depth + 1) for child in children)
                except (OSError, UnicodeError, subprocess.SubprocessError):
                    self.warning(directory, 'unreadable_or_invalid_git')
            if source_identity(parent) != identity:
                raise ValueError('Discovery parent changed. Choose it again.')
        except (OSError, ValueError) as error:
            final = 'failed'
            self.warning(parent, 'git_unavailable' if not git else 'parent_unavailable')
        with self.lock:
            self.job['state'] = final
            self.job['incomplete'] |= final != 'complete'
            if self.diagnostics:
                self.diagnostics.emit('git_discovery', result='failed' if final == 'failed' else
                                      'partial' if self.job['incomplete'] else 'complete',
                                      repo_count=len(self.job['results']),
                                      duration_ms=(time.monotonic() - started) * 1000)
