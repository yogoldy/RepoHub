"""Reviewed first-run configuration; filesystem changes have a recovery journal."""
import copy
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time

from access_checks import probe_source
from backup_layout import BackupLayout, LayoutTransaction, readable_paths, folded
from backup_policy import validate_settings
from destination_policy import inspect_destination, require_destination
from workspace_registry import WorkspaceRegistry, source_identity


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class SetupService:
    def __init__(self, hub, writer):
        self.hub, self.writer = hub, writer
        self.lock = threading.RLock()
        self.operation = {'state': 'idle'}
        self.receipt = None

    def revision(self):
        paths = ['data/workspace-registry.json', 'data/settings.json', 'data/setup.json',
                 'data/backup-layout.json', 'backups.json']
        contents = {}
        for name in paths:
            path = self.hub.state_dir / name
            if path.is_symlink():
                raise ValueError('Configuration file is redirected')
            contents[name] = path.read_text() if path.exists() else None
        return digest(contents)

    def status(self):
        hub = self.hub
        current = hub.registry.status()['configuration']
        source = ({'mode': 'home', 'home': current['source']['home']}
                  if current['source']['mode'] == 'home' else
                  {'mode': 'manual', 'paths': [row['path'] for row in current['workspaces'] if row['active']]})
        return {'configured': hub.configured, 'reviewed': hub.setup_record.get('reviewed', False),
                'source': source, 'destination': str(hub.backups) if hub.configured else '',
                'workspaces': [row for row in current['workspaces'] if row['active']],
                'settings': copy.deepcopy(hub.settings), 'revision': self.revision(),
                'discovery_parent': hub.setup_record.get('discovery_parent', ''),
                'previous_destinations': hub.setup_record.get('previous_destinations', []),
                'recovery_required': hub.setup_recovery_required}

    def candidate(self, payload):
        if set(payload) != {'source', 'destination', 'settings', 'revision', 'discovery_parent'}:
            raise ValueError('Invalid setup request')
        if payload['revision'] != self.revision():
            raise FileExistsError('Configuration changed. Reload setup and review again.')
        settings = validate_settings(payload['settings'])
        parent = payload['discovery_parent']
        if not isinstance(parent, str) or (parent and (not Path(parent).is_absolute() or '\x00' in parent)):
            raise ValueError('Invalid discovery parent')
        hub = self.hub
        # Validate the draft against both destinations without mutating the active registry.
        registry = object.__new__(WorkspaceRegistry)
        registry.value = copy.deepcopy(hub.registry.value)
        registry.protected = (*hub.registry.protected, Path(payload['destination']).resolve())
        configuration = registry.candidate(payload['source'])
        active = [row for row in configuration['workspaces'] if row['active']]
        if not active:
            raise ValueError('Choose at least one folder before finishing setup')
        required = 16 * 1024 * 1024
        for row in active:
            probe_source(row['path'])
            for directory, _, files in os.walk(row['path'], followlinks=False,
                                                          onerror=lambda error: (_ for _ in ()).throw(error)):
                required += sum((Path(directory) / name).lstat().st_size for name in files)
        destination = inspect_destination(payload['destination'], [row['path'] for row in active],
                                          hub.state_dir, cloud_root=hub.setup_cloud_root,
                                          required_bytes=required)
        names = readable_paths(configuration['workspaces'])
        owned = {hub.layout.directory(key) for key, value in hub.index.items()
                 if hub.layout.contains(key, value['archive'])}
        for name in names.values():
            target = Path(destination['path']) / name
            LayoutTransaction.safe_target(Path(destination['path']), target)
            if target.exists() and (Path(destination['path']) != hub.backups or target not in owned):
                raise FileExistsError('The destination already contains an unowned backup folder: ' + str(target))
        stable = {'configuration': configuration, 'destination': {
            'path': destination['path'], 'identity': destination['identity']},
            'settings': settings, 'names': names, 'discovery_parent': parent}
        return stable, destination

    def review(self, payload):
        self.receipt = None
        stable, destination = self.candidate(payload)
        token = digest({'revision': payload['revision'], **stable})
        if payload['revision'] != self.revision():
            raise FileExistsError('Configuration changed during access checks. Review again.')
        self.receipt = {'token': token, 'payload': copy.deepcopy(payload), 'checked_at': time.monotonic()}
        rows = stable['configuration']['workspaces']
        current = {row['id'] for row in rows if row['active']}
        return {'review': token, 'workspaces': [
            {**row, 'backup_path': str(Path(destination['path']) / stable['names'][row['id']]),
             'access': 'accessible'} for row in rows if row['active']],
            'removed': [row for row in self.hub.registry.value['workspaces']
                        if row['active'] and row['id'] not in current],
            'destination': destination, 'destination_changed': destination['path'] != str(self.hub.backups),
            'previous_destination': str(self.hub.backups) if self.hub.configured else None,
            'access': 'accessible', 'settings': stable['settings']}

    def apply(self, payload):
        if set(payload) != {'draft', 'review', 'backup_now'} or type(payload['backup_now']) is not bool:
            raise ValueError('Invalid setup save')
        receipt = self.receipt
        if (not receipt or receipt['token'] != payload['review'] or receipt['payload'] != payload['draft']
                or time.monotonic() - receipt['checked_at'] > 600):
            raise FileExistsError('Check access and review this exact setup before saving')
        hub = self.hub
        if not hub.backup_lock.acquire(blocking=False):
            raise FileExistsError('A backup is running. Finish setup after it completes.')
        if not hub.scan_lock.acquire(blocking=False):
            hub.backup_lock.release()
            raise FileExistsError('A scan is running. Try again after it finishes.')
        hub.lock.acquire()
        transaction = LayoutTransaction(hub.state_dir, self.writer)
        try:
            stable, destination = self.candidate(payload['draft'])
            if digest({'revision': payload['draft']['revision'], **stable}) != payload['review']:
                raise FileExistsError('Selected folders changed. Check access and review again.')
            root = Path(destination['path'])
            index = copy.deepcopy(hub.index)
            moves = []
            if root == hub.backups:
                for key, name in stable['names'].items():
                    old = hub.layout.directory(key) if hub.layout.names is None or key in hub.layout.names else None
                    if old is None or old == root / name or not old.exists():
                        continue
                    current = index.get(key)
                    if not current or Path(current['archive']).parent != old:
                        continue  # Never adopt or rename an unowned directory.
                    if hub.archive_digest(current['archive']) != current['sha256']:
                        raise ValueError('Current archive failed verification; migration stopped')
                    moves.append((str(old.relative_to(root)), name))
                    current['archive'] = str(root / name / Path(current['archive']).name)
            previous = list(hub.setup_record.get('previous_destinations', []))
            if hub.configured and root != hub.backups and str(hub.backups) not in previous:
                previous.append(str(hub.backups))
            record = {'version': 1, 'configured': True, 'reviewed': True,
                      'destination': {'path': destination['path'], 'identity': destination['identity']},
                      'discovery_parent': stable['discovery_parent'], 'previous_destinations': previous}
            updates = {'data/workspace-registry.json': stable['configuration'],
                       'data/settings.json': stable['settings'], 'data/backup-layout.json': stable['names'],
                       'data/setup.json': record, 'backups.json': index, '@destination-index': index}
            if not hub.configured:
                updates['schedule-clock.json'] = {'last_periodic_at': time.time(), 'repos': {}}
            transaction.begin(root, moves, updates)
            self.reload()
            self.receipt = None
            hub.diagnostics.emit('setup_applied', result='saved', repo_count=len(hub.repositories()))
        finally:
            hub.setup_recovery_required = transaction.path.exists()
            hub.lock.release()
            hub.scan_lock.release()
            hub.backup_lock.release()
        hub.scan(deep=False)
        if payload['backup_now']:
            threading.Thread(target=hub.backup, daemon=True).start()
        return self.status()

    def reload(self):
        hub = self.hub
        hub.setup_record = json.loads((hub.data_dir / 'setup.json').read_text())
        hub.configured = True
        hub.backups = Path(hub.setup_record['destination']['path'])
        hub.registry.protected = (hub.backups, hub.state_dir,
                                  *(Path(path) for path in hub.setup_record.get('previous_destinations', [])))
        hub.registry.value = hub.registry.validate(json.loads(hub.registry.path.read_text()))
        hub.settings = validate_settings(json.loads(hub.settings_path.read_text()))
        hub.index = json.loads((hub.state_dir / 'backups.json').read_text())
        hub.layout = BackupLayout(hub.state_dir, hub.backups)
        clock = json.loads((hub.state_dir / 'schedule-clock.json').read_text()) if (hub.state_dir / 'schedule-clock.json').exists() else {}
        hub.last_periodic_at = clock.get('last_periodic_at', hub.last_periodic_at)
        hub.repo_periodic_at = clock.get('repos', hub.repo_periodic_at)
        hub.verifications.clear(); hub.cloud_states.clear()
        hub.status['backup_root'] = str(hub.backups)
        hub.discovery.protected = hub.registry.protected

    def continue_current(self, payload):
        if set(payload) != {'revision'} or payload['revision'] != self.revision() or not self.hub.configured:
            raise FileExistsError('Reload setup before continuing with current settings')
        if self.snapshot()['state'] in {'checking', 'applying'}:
            raise FileExistsError('Wait for the current setup operation')
        record = {**self.hub.setup_record, 'version': 1, 'configured': True, 'reviewed': True}
        self.writer(self.hub.data_dir / 'setup.json', record)
        self.hub.setup_record = record
        self.hub.diagnostics.emit('setup_continued', result='kept')
        return self.status()

    def allocate(self, key, path):
        """Home auto-discovery may add unambiguous names, never rename other backups."""
        layout = self.hub.layout
        if layout.names is not None and key not in layout.names:
            names = {**layout.names, key: Path(path).name}
            candidate = folded(Path(path).name)
            if any(other != key and (folded(value) == candidate or folded(value).startswith(candidate + '/')
                    or candidate.startswith(folded(value) + '/')) for other, value in names.items()):
                raise ValueError('Backup folder names conflict. Review setup for readable parent grouping.')
            if candidate.startswith('.repohub') or candidate == 'index.json':
                raise ValueError('Review setup to resolve this reserved backup folder name')
            if (layout.root / Path(path).name).exists():
                raise FileExistsError('The new backup folder is already occupied. Review setup.')
            self.writer(layout.path, names)
            layout.names = names
        return layout.directory(key)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.operation)

    def start(self, kind, payload):
        if kind not in {'review', 'apply'}:
            raise ValueError('Unknown setup operation')
        with self.lock:
            if self.operation['state'] in {'checking', 'applying'}:
                raise FileExistsError('Setup operation is already running')
            self.operation = {'id': secrets.token_hex(12), 'state': 'checking' if kind == 'review' else 'applying'}
            snapshot = self.snapshot()
            threading.Thread(target=self.run, args=(kind, copy.deepcopy(payload)), daemon=True).start()
            return snapshot

    def run(self, kind, payload):
        try:
            value = self.review(payload) if kind == 'review' else self.apply(payload)
            with self.lock:
                self.operation.update(state='complete', value=value)
            if kind == 'review':
                self.hub.diagnostics.emit('setup_review', result='complete', repo_count=len(value['workspaces']))
        except Exception as error:
            with self.lock:
                self.operation.update(state='failed', error=str(error), conflict=isinstance(error, FileExistsError))
            self.hub.diagnostics.emit('setup_review' if kind == 'review' else 'setup_applied',
                                      result='failed', error_type=type(error).__name__)
