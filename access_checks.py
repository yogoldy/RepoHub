"""Typed I/O outcomes; an errno is not proof of a macOS privacy decision."""
import errno
import json
import os
from pathlib import Path
import stat
import tempfile


def access_failure(error, operation):
    code = getattr(error, 'errno', None)
    if code == errno.ESTALE:
        state, detail = 'changed', 'Folder identity changed. Review and save the folder selection before backing it up.'
    elif code in (errno.EACCES, errno.EPERM):
        state, detail = 'blocked', 'Access denied. Check folder permissions and macOS Privacy & Security, then retry.'
    elif code in (errno.ENOENT, errno.ENODEV, errno.ENXIO, errno.ENOTDIR):
        state, detail = 'unavailable', 'Folder or storage unavailable. Reconnect it or review the selected path, then retry.'
        if operation == 'source_read':
            detail = ('Folder unavailable. Reconnect it if needed, or open Settings → Folders to back up '
                      'and review and save your selection if it was removed.')
    elif code in (errno.ENOSPC, errno.EDQUOT, errno.EROFS):
        state, detail = 'blocked', 'Storage is full or read-only. Make space or restore write access, then retry.'
    else:
        state, detail = 'error', 'I/O failed. Check storage and retry; the previous verified backup is retained.'
    return {'state': state, 'operation': operation, 'error_code': code, 'detail': detail}


def probe_source(path):
    # Open each regular file without following symlinks. This tests access, not hashes.
    for directory, dirs, files in os.walk(path, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
        for name in dirs + files:
            item = Path(directory)/name
            info = item.lstat()
            if stat.S_ISREG(info.st_mode):
                fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW)
                try:os.read(fd, 1)
                finally:os.close(fd)


def probe_destination(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise FileNotFoundError(errno.ENOENT, 'Backup destination unavailable')
    fd, raw = tempfile.mkstemp(prefix='.repohub-access-',dir=path)
    try:
        os.write(fd,b'RepoHub access check');os.fsync(fd)
    finally:
        os.close(fd);Path(raw).unlink()


# The native app writes login-item.json beside the helper's state; it alone can ask macOS.
_LOGIN_STATES = {'enabled': 'registered', 'legacyAgent': 'registered',
                 'notRegistered': 'not_registered', 'requiresApproval': 'requires_approval'}


def login_state(state_dir):
    """Whether the app starts at login: registered, not_registered, requires_approval or unknown."""
    path = Path(state_dir) / 'login-item.json'
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            return 'unknown'
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return 'unknown'
    state = value.get('state') if isinstance(value, dict) else None
    return _LOGIN_STATES.get(state, 'unknown') if isinstance(state, str) else 'unknown'
