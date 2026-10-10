"""Typed I/O outcomes; an errno is not proof of a macOS privacy decision."""
import errno
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
