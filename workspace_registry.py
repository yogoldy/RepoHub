"""Validated source selection and persistent identity; never edits source folders."""
import hashlib
import json
from pathlib import Path
import re
import threading

ID = re.compile(r'^[a-zA-Z0-9_-]{1,80}$')


def workspace_id(name):
    slug = re.sub(r'[^a-zA-Z0-9_-]', '-', name).strip('-')[:45] or 'repo'
    return slug + '-' + hashlib.sha256(name.encode()).hexdigest()[:10]


def canonical(value):
    if not isinstance(value, str) or not value or '\x00' in value or not Path(value).is_absolute():
        raise ValueError('Choose an absolute folder path')
    return Path(value).resolve()


def same_location(a, b):
    if a == b:
        return True
    try:
        return a.samefile(b)
    except OSError:
        return False


def overlaps(a, b):
    return (any(same_location(a, p) for p in (b, *b.parents))
            or any(same_location(b, p) for p in a.parents))


class WorkspaceRegistry:
    def __init__(self, path, legacy_home, protected, writer, initial_source=None):
        self.path = Path(path)
        self.protected = tuple(Path(p).resolve() for p in protected)
        self.writer = writer
        self.lock = threading.RLock()
        if self.path.is_symlink():
            raise ValueError('Unsafe workspace registry')
        if self.path.exists():
            self.value = self.validate(json.loads(self.path.read_text()))
        else:
            home = canonical(str(legacy_home)) if legacy_home is not None else None
            if home is None:
                self.value = {'schema_version': 1, 'source': {'mode': 'manual'}, 'workspaces': []}
                self.value = self.candidate(initial_source)
            else:
                self.safe_source(home)
                self.value = {'schema_version': 1, 'source': {'mode': 'home', 'home': str(home)}, 'workspaces': []}
            # Preserve all existing name-derived IDs during migration; even an
            # empty legacy home can acquire children later without changing IDs.
            self.value = self.discover(self.value)
            self.writer(self.path, self.value)
        self.refresh()

    def safe_source(self, path):
        if any(overlaps(path, other) for other in self.protected):
            raise ValueError('Sources must not overlap backup or application-state folders')

    def validate(self, value):
        if not isinstance(value, dict) or set(value) != {'schema_version', 'source', 'workspaces'} or type(value['schema_version']) is not int or value['schema_version'] != 1:
            raise ValueError('Invalid workspace registry')
        source = value['source']
        if not isinstance(source, dict) or source.get('mode') not in {'home', 'manual'}:
            raise ValueError('Invalid source mode')
        if source['mode'] == 'home':
            if set(source) != {'mode', 'home'}:
                raise ValueError('Invalid repo-home configuration')
            home = canonical(source['home'])
            if str(home) != source['home']:
                raise ValueError('Repo home has changed its canonical location')
            self.safe_source(home)
        elif set(source) != {'mode'}:
            raise ValueError('Invalid manual configuration')
        rows = value['workspaces']
        if not isinstance(rows, list):
            raise ValueError('Invalid workspace list')
        ids, paths, active = set(), set(), []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'id', 'path', 'active'} or not isinstance(row['id'], str) or not ID.fullmatch(row['id']) or row['id'] == 'repohub-data' or type(row['active']) is not bool:
                raise ValueError('Invalid workspace entry')
            # Preserve canonical strings for absent folders; reject retargeted
            # symlinks instead of silently adopting a different source.
            raw = row['path']
            if not isinstance(raw, str) or not Path(raw).is_absolute() or '\x00' in raw or str(Path(raw)) != raw or '..' in Path(raw).parts:
                raise ValueError('Invalid saved workspace path')
            path = Path(raw)
            self.safe_source(path)
            if row['id'] in ids or raw in paths:
                raise ValueError('Duplicate workspace identity')
            ids.add(row['id']); paths.add(raw)
            if row['active']:
                if source['mode'] == 'home' and not same_location(path.parent, home):
                    raise ValueError('Repo-home entries must be immediate children')
                if any(overlaps(path, other) for other in active):
                    raise ValueError('Selected workspace folders overlap')
                active.append(path)
        return value

    def discover(self, value):
        value = json.loads(json.dumps(value))
        if value['source']['mode'] != 'home':
            return value
        home = Path(value['source']['home'])
        if not home.exists():
            return value  # Keep missing sources visible; do not erase identity.
        if home.resolve() != home or not home.is_dir():
            raise ValueError('Repo home is unavailable or has changed location')
        by_path = {row['path']: row for row in value['workspaces']}
        ids = {row['id'] for row in value['workspaces']}
        for path in sorted(home.iterdir(), key=lambda p: str(p).lower()):
            if path.name.startswith('.') or path.is_symlink() or not path.is_dir():
                continue
            self.safe_source(path)
            row = by_path.get(str(path))
            if row:
                row['active'] = True
            else:
                key = workspace_id(path.name)
                if key in ids:
                    key = workspace_id(str(path))
                if key in ids:
                    raise ValueError('Workspace identity collision')
                row = {'id': key, 'path': str(path), 'active': True}
                value['workspaces'].append(row); ids.add(key)
        return self.validate(value)

    def refresh(self):
        with self.lock:
            updated = self.discover(self.value)
            if updated != self.value:
                self.writer(self.path, updated)
                self.value = updated
            return {row['id']: Path(row['path']) for row in self.value['workspaces'] if row['active']}

    def revision(self):
        if self.path.is_symlink():
            raise ValueError('Unsafe workspace registry')
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def status(self):
        with self.lock:
            self.refresh()
            return {'configuration': json.loads(json.dumps(self.value)), 'revision': self.revision()}

    def candidate(self, source):
        if not isinstance(source, dict):
            raise ValueError('Invalid source selection')
        mode = source.get('mode')
        if mode == 'home' and set(source) == {'mode', 'home'}:
            home = canonical(source['home']); self.safe_source(home)
            if not home.is_dir():
                raise ValueError('Choose an accessible repo-home folder')
            selected = {'mode': 'home', 'home': str(home)}
            paths = [p for p in sorted(home.iterdir()) if p.is_dir() and not p.is_symlink() and not p.name.startswith('.')]
        elif mode == 'manual' and set(source) == {'mode', 'paths'} and isinstance(source['paths'], list):
            selected = {'mode': 'manual'}
            paths = []
            for raw in source['paths']:
                path = canonical(raw)
                if not any(same_location(path, other) for other in paths):
                    paths.append(path)
        else:
            raise ValueError('Choose repo-home or manual source selection')
        for path in paths:
            self.safe_source(path)
            if not path.is_dir():
                raise ValueError('Choose existing workspace folders')
        rows = json.loads(json.dumps(self.value['workspaces']))
        by_path = {r['path']: r for r in rows}; ids = {r['id'] for r in rows}
        for row in rows:
            row['active'] = False
        for path in paths:
            previous = by_path.get(str(path)) or next((r for r in rows if same_location(Path(r['path']), path)), None)
            if previous:
                previous['active'] = True
            else:
                key = workspace_id(str(path))
                if key in ids:
                    raise ValueError('Workspace identity collision')
                rows.append({'id': key, 'path': str(path), 'active': True}); ids.add(key)
        return self.validate({'schema_version': 1, 'source': selected, 'workspaces': rows})

    def review(self, source, revision):
        with self.lock:
            self.refresh()
            if revision != self.revision():
                raise FileExistsError('Workspace selection changed. Reopen setup and review it again.')
            candidate = self.candidate(source)
            active = [r for r in candidate['workspaces'] if r['active']]
            selected = {r['id'] for r in active}
            removed = [r for r in self.value['workspaces'] if r['active'] and r['id'] not in selected]
            digest = hashlib.sha256(json.dumps(candidate, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            return {'source': source, 'revision': revision, 'review': digest,
                    'workspaces': active, 'removed': removed}

    def save(self, source, revision, review=None):
        with self.lock:
            self.refresh()
            if revision != self.revision():
                raise FileExistsError('Workspace selection changed. Review it again before saving.')
            value = self.candidate(source)
            if review is not None:
                current = self.review(source, revision)
                if not isinstance(review, str) or review != current['review']:
                    raise FileExistsError('The folder list changed. Review it again before saving.')
            self.writer(self.path, value)
            self.value = value
            return self.status()


def require_source(path, canonical_only=False):
    path = Path(path)
    if path.is_symlink() or (canonical_only and path.resolve() != path) or not path.is_dir():
        raise FileNotFoundError('Workspace folder is unavailable or its location changed')
