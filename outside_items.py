"""Find content a repo points to outside its folder and keep reviewed choices.

Detection reads link text and Git's worktree registrations from the scan's
existing inventory. It never copies, follows into or changes outside content.
Choices are recorded here; the helper archives included folders separately.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

from workspace_registry import overlaps

SYSTEM_PREFIXES = ('/opt/', '/usr/', '/System/', '/Library/', '/Applications/',
                   '/bin/', '/sbin/', '/etc/', '/private/etc/')
MAX_ADMIN_BYTES = 4096
LINK_CHOICES = ('link_only', 'include')
CHECKOUT_CHOICES = ('committed_only', 'include')
REPO_KEY = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
BROAD = (Path('/'), Path('/Users'), Path('/Volumes'))
REFUSALS = {
    'not_a_directory': 'its link no longer points to a folder',
    'too_broad': 'it is a top-level or home folder',
    'system_location': 'it is a system or installed-tool folder',
    'app_state': "it overlaps RepoHub's own data",
    'backup_destination': 'it overlaps a backup destination',
    'inside_monitored_repo': 'it overlaps a monitored repo, which is backed up on its own',
    'duplicate_target': 'another included link already covers that folder',
}


def link_scope(relative, target):
    """Classify link text lexically; the target is not consulted."""
    if PurePosixPath(target).is_absolute():
        return 'absolute'
    parts = list(PurePosixPath(relative).parent.parts)
    for part in target.split('/'):
        if part == '..':
            if not parts:
                return 'relative_escaping'
            parts.pop()
        elif part not in ('', '.'):
            parts.append(part)
    return 'inside'


def classify_link(root, relative, target):
    if link_scope(relative, target) == 'inside':
        return None
    resolved = os.path.normpath(os.path.join(str(root), os.path.dirname(relative), target))
    try:
        info = os.stat(Path(root) / relative)
    except OSError:
        kind = 'missing'
    else:
        kind = ('directory' if stat.S_ISDIR(info.st_mode)
                else 'file' if stat.S_ISREG(info.st_mode) else 'other')
    # Folders can be included later. Single files and system tools are reinstalled instead.
    category = ('linked_folder' if kind == 'directory'
                and not (resolved + '/').startswith(SYSTEM_PREFIXES) else 'reinstall')
    return {'path': relative, 'target': target, 'resolved': resolved,
            'target_type': kind, 'category': category}


def read_admin(path):
    """Read one small regular Git administrative file without following links."""
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_ADMIN_BYTES:
        return None
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        raw = source.read(MAX_ADMIN_BYTES + 1)
    try:
        value = raw.decode('utf-8')
    except UnicodeDecodeError:
        return None
    value = value[:-1] if value.endswith('\n') else value
    if not value or any(character in value for character in '\n\r\x00'):
        return None
    return value


def linked_checkouts(root):
    admin = Path(root) / '.git' / 'worktrees'
    if admin.is_symlink() or not admin.is_dir():
        return []
    result = []
    for registration in sorted(admin.iterdir()):
        if registration.is_symlink() or not registration.is_dir():
            continue
        pointer = read_admin(registration / 'gitdir')
        if pointer is None or PurePosixPath(pointer).name != '.git':
            result.append({'name': registration.name, 'path': None, 'state': 'invalid'})
            continue
        marker = Path(pointer) if os.path.isabs(pointer) else registration / pointer
        checkout = Path(os.path.normpath(str(marker))).parent
        present = (checkout.is_dir() and not checkout.is_symlink()
                   and (checkout / '.git').is_file())
        result.append({'name': registration.name, 'path': str(checkout),
                       'state': 'present' if present else 'removed'})
    return result


def detect(root, entries):
    links = []
    for relative, mode, _size, _mtime, target in entries:
        # Git-internal links are a restore-protocol question, not a user choice.
        if not stat.S_ISLNK(mode) or '.git' in PurePosixPath(relative).parts:
            continue
        item = classify_link(root, relative, target)
        if item:
            links.append(item)
    return {'links': links, 'checkouts': linked_checkouts(root)}


def counts(detected):
    links, checkouts = detected['links'], detected['checkouts']
    return {'linked_folders': sum(item['category'] == 'linked_folder' for item in links),
            'reinstall': sum(item['category'] == 'reinstall' for item in links),
            'checkouts': sum(item['state'] == 'present' for item in checkouts),
            'removed_checkouts': sum(item['state'] != 'present' for item in checkouts)}


def included_folders(detected, choices):
    """Linked folders whose saved choice is include and whose link is still present."""
    chosen = choices.get('linked_folders', {})
    return [item for item in detected['links']
            if item['category'] == 'linked_folder' and chosen.get(item['path']) == 'include']


def inclusion_target(link, repositories=(), destinations=(), state=None, seen=None):
    """Resolve a reviewed link's folder, or return why it cannot be archived separately."""
    try:
        real = Path(link).resolve(strict=True)
        info = os.stat(real)
    except (OSError, RuntimeError):
        return None, 'not_a_directory'
    if not stat.S_ISDIR(info.st_mode):
        return None, 'not_a_directory'
    if real in BROAD or real == Path.home():
        return None, 'too_broad'
    if (str(real) + '/').startswith(SYSTEM_PREFIXES):
        return None, 'system_location'
    if state is not None and overlaps(real, Path(state)):
        return None, 'app_state'
    if any(overlaps(real, Path(path)) for path in destinations):
        return None, 'backup_destination'
    if any(overlaps(real, Path(path)) for path in repositories):
        return None, 'inside_monitored_repo'
    if seen and any(overlaps(real, Path(path)) for path in seen):
        return None, 'duplicate_target'
    return real, None


def refusal_text(path, reason):
    return path + ' cannot be included: ' + REFUSALS[reason] + '.'


def folder_size(path, max_entries=200000, max_seconds=3.0):
    """Bounded metadata walk; an incomplete total is reported as a lower bound."""
    total = entries = 0
    complete = True
    started = time.monotonic()
    try:
        for directory, dirs, files in os.walk(path, followlinks=False):
            for name in files:
                try:
                    info = os.lstat(os.path.join(directory, name))
                except OSError:
                    complete = False
                    continue
                if stat.S_ISREG(info.st_mode):
                    total += info.st_size
            entries += len(dirs) + len(files)
            if entries > max_entries or time.monotonic() - started > max_seconds:
                complete = False
                break
    except OSError:
        complete = False
    return {'bytes': total, 'complete': complete}


def review(detected, git_status, refusals=None):
    def public(item):
        return {key: item[key] for key in ('path', 'target', 'target_type')}
    refusals = refusals or {}
    folders = []
    for item in detected['links']:
        if item['category'] != 'linked_folder':
            continue
        row = {**public(item), **folder_size(item['resolved'])}
        if item['path'] in refusals:
            row['blocked'] = REFUSALS[refusals[item['path']]]
        folders.append(row)
    reinstall = [public(item) for item in detected['links'] if item['category'] == 'reinstall']
    checkouts = []
    for item in detected['checkouts']:
        row = dict(item)
        if item['state'] == 'present':
            row.update(folder_size(item['path']))
            try:
                row['changed_files'] = git_status(Path(item['path'])).get('changed_files')
            except (OSError, ValueError, Exception):
                row['changed_files'] = None
        checkouts.append(row)
    return {'linked_folders': folders, 'reinstall': reinstall, 'checkouts': checkouts}


def valid_link_path(value):
    return (isinstance(value, str) and 0 < len(value) <= 1024 and '\x00' not in value
            and not PurePosixPath(value).is_absolute()
            and all(part not in ('', '.', '..') for part in value.split('/')))


def validate_repo(item, known=None):
    if not isinstance(item, dict) or set(item) != {'linked_folders', 'checkouts'}:
        raise ValueError('Invalid outside-item choices')
    folders = item['linked_folders']
    if not isinstance(folders, dict):
        raise ValueError('Invalid outside-item choices')
    for path, choice in folders.items():
        if not valid_link_path(path) or choice not in LINK_CHOICES:
            raise ValueError('Invalid linked-folder choice')
        if known is not None and path not in known:
            raise ValueError('Unknown linked folder. Rescan this repo before saving.')
    if item['checkouts'] not in CHECKOUT_CHOICES:
        raise ValueError('Invalid linked-checkout choice')


class OutsideChoices:
    """Per-repo choices in one revision-checked file."""
    def __init__(self, path, writer):
        self.path, self.writer = Path(path), writer

    def raw(self):
        if self.path.is_symlink():
            raise ValueError('Outside-item choices file is redirected')
        return self.path.read_bytes() if self.path.exists() else None

    def revision(self):
        raw = self.raw()
        return hashlib.sha256(raw).hexdigest() if raw is not None else 'none'

    def load(self):
        raw = self.raw()
        value = json.loads(raw) if raw is not None else {}
        if not isinstance(value, dict):
            raise ValueError('Invalid outside-item choices')
        for key, item in value.items():
            if not isinstance(key, str) or not REPO_KEY.fullmatch(key):
                raise ValueError('Invalid outside-item choices')
            validate_repo(item)
        return value

    def for_repo(self, key, detected):
        folders = {item['path']: 'link_only' for item in detected['links']
                   if item['category'] == 'linked_folder'}
        stored = self.load().get(key)
        checkouts = 'committed_only'
        if stored:
            folders.update({path: choice for path, choice in stored['linked_folders'].items()
                            if path in folders})
            checkouts = stored['checkouts']
        return {'linked_folders': folders, 'checkouts': checkouts}

    def save(self, key, choices, revision, known):
        validate_repo(choices, known)
        if revision != self.revision():
            raise FileExistsError('Choices changed. Reopen this page before saving.')
        updated = dict(self.load())
        updated[key] = {'linked_folders': dict(choices['linked_folders']),
                        'checkouts': choices['checkouts']}
        self.writer(self.path, updated)
