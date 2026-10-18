"""Readable destination paths and recoverable, non-destructive layout changes."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import unicodedata


def folded(value):
    return unicodedata.normalize('NFC', value).casefold()


def relative_path(value):
    if not isinstance(value, str):
        raise ValueError('Invalid backup folder layout')
    path = Path(value)
    if (path.is_absolute() or not path.parts
            or str(path) != value or any(part in {'.', '..'} for part in path.parts)):
        raise ValueError('Invalid backup folder layout')
    return path


def readable_paths(workspaces):
    """Add the shortest parent suffix only where names or hierarchy collide."""
    sources = {row['id']: Path(row['path']) for row in workspaces}
    depths = {key: 1 for key in sources}
    for _ in range(max((len(path.parts) for path in sources.values()), default=1) + 1):
        names = {key: '/'.join(path.parts[-depths[key]:]) for key, path in sources.items()}
        collisions = set()
        for key, name in names.items():
            if folded(name).startswith('.repohub') or folded(name) == 'index.json':
                collisions.add(key)
            for other, candidate in names.items():
                if key != other and (folded(candidate) == folded(name)
                        or folded(candidate).startswith(folded(name) + '/')):
                    collisions.update((key, other))
        if not collisions:
            for name in names.values():
                relative_path(name)
            return {**names, 'repohub-data': '.repohub-data'}
        for key in collisions:
            depths[key] += 1
            if depths[key] >= len(sources[key].parts):
                raise ValueError('Backup names conflict. Review the source folder paths.')
    raise ValueError('Cannot create a safe backup layout')


def tree_hashes(root):
    """Do not migrate symlinks, placeholders that cannot be read, or foreign trees."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Backup folder is unavailable or redirected')
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False,
                                         onerror=lambda error: (_ for _ in ()).throw(error)):
        for name in dirs + files:
            item = Path(directory) / name
            if item.is_symlink():
                raise ValueError('Linked backup entries cannot be migrated')
        for name in files:
            item = Path(directory) / name
            if not stat.S_ISREG(item.lstat().st_mode):
                raise ValueError('Unsupported backup entry')
            digest = hashlib.sha256()
            with item.open('rb') as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
            result[str(item.relative_to(root))] = digest.hexdigest()
    return result


class LayoutTransaction:
    """Finish journaled renames before exposing any of the new configuration.

    All moves stay on one filesystem. All old directories are staged first so a
    readable name equal to another legacy ID cannot overwrite that directory.
    Recovery rolls forward; failures leave the journal and every archive intact.
    """
    def __init__(self, state, writer):
        self.state = Path(state)
        self.path = self.state / 'layout-transaction.json'
        self.writer = writer

    def begin(self, root, moves, updates):
        if self.path.exists():
            raise FileExistsError('An earlier setup transaction needs recovery')
        root = Path(root)
        if root.is_symlink() or not root.is_dir() or root.resolve() != root:
            raise ValueError('Backup destination is unavailable or redirected')
        plan = []
        for old, new in moves:
            old, new = relative_path(old), relative_path(new)
            if old == new or not (root / old).exists():
                continue
            plan.append({'old': str(old), 'new': str(new), 'hashes': tree_hashes(root / old)})
        old_paths = {entry['old'] for entry in plan}
        for entry in plan:
            target = root / entry['new']
            if target.exists() and entry['new'] not in old_paths:
                raise FileExistsError('A backup folder already occupies the reviewed destination')
            self.safe_target(root, target)
        for name in updates:
            relative_path(name)
        journal = {'version': 1, 'root': str(root), 'stage': '.repohub-migration-' + secrets.token_hex(12),
                   'phase': 'stage', 'moves': plan, 'updates': updates}
        self.writer(self.path, journal)
        self.recover()

    @staticmethod
    def safe_target(root, target):
        if root not in target.parents:
            raise ValueError('Backup path escaped destination')
        for parent in (target, *target.parents):
            if parent == root:
                break
            if parent.is_symlink() or (parent.exists() and parent.resolve() != parent):
                raise ValueError('Backup folder is redirected')

    def recover(self):
        if not self.path.exists():
            return False
        if self.path.is_symlink():
            raise ValueError('Unsafe setup journal')
        journal = json.loads(self.path.read_text())
        root = Path(journal['root'])
        stage = root / relative_path(journal['stage'])
        if (journal.get('version') != 1 or not stage.name.startswith('.repohub-migration-')
                or root.resolve() != root or root.is_symlink() or not root.is_dir()):
            raise ValueError('Setup recovery destination is unavailable')
        self.safe_target(root, stage)
        stage.mkdir(exist_ok=True, mode=0o700)
        if journal['phase'] == 'stage':
            for number, entry in enumerate(journal['moves']):
                old = root / relative_path(entry['old'])
                temporary = stage / str(number)
                self.safe_target(root, old)
                if not temporary.exists():
                    if tree_hashes(old) != entry['hashes']:
                        raise ValueError('Backup changed before migration')
                    old.rename(temporary)
                if tree_hashes(temporary) != entry['hashes']:
                    raise ValueError('Staged backup verification failed')
            journal['phase'] = 'publish'
            self.writer(self.path, journal)
        if journal['phase'] != 'publish':
            raise ValueError('Invalid setup recovery phase')
        for number, entry in enumerate(journal['moves']):
            target = root / relative_path(entry['new'])
            self.safe_target(root, target)
            temporary = stage / str(number)
            if temporary.exists():
                if target.exists():
                    raise FileExistsError('Reviewed backup path became occupied')
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary.rename(target)
            if tree_hashes(target) != entry['hashes']:
                raise ValueError('Migrated backup verification failed')
        # A journal is never removed until every configuration write has succeeded.
        for name, value in journal['updates'].items():
            relative = relative_path(name)
            target = root / 'index.json' if name == '@destination-index' else self.state / relative
            self.safe_target(root if name == '@destination-index' else self.state, target)
            self.writer(target, value)
        stage.rmdir()
        self.path.unlink()
        return True


class BackupLayout:
    def __init__(self, state, root):
        self.path = Path(state) / 'data/backup-layout.json'
        self.root = Path(root)
        if self.path.is_symlink():
            raise ValueError('Unsafe backup layout metadata')
        self.names = json.loads(self.path.read_text()) if self.path.exists() else None
        if self.names is not None:
            if not isinstance(self.names, dict):
                raise ValueError('Invalid backup layout metadata')
            for value in self.names.values():
                relative_path(value)

    def directory(self, key):
        if self.names is not None and key not in self.names:
            raise ValueError('Review setup to assign this repo a readable backup folder')
        target = self.root / relative_path(self.names[key] if self.names is not None else key)
        LayoutTransaction.safe_target(self.root, target)
        return target

    def contains(self, key, archive):
        return Path(archive).parent == self.directory(key)
