"""Typed I/O outcomes; an errno is not proof of a macOS privacy decision."""
import errno


def access_failure(error, operation):
    code = getattr(error, 'errno', None)
    if code in (errno.EACCES, errno.EPERM):
        state, detail = 'blocked', 'Access denied. Check folder permissions and macOS Privacy & Security, then retry.'
    elif code in (errno.ENOENT, errno.ENODEV, errno.ENXIO, errno.ENOTDIR):
        state, detail = 'unavailable', 'Folder or storage unavailable. Reconnect it or review the selected path, then retry.'
    elif code in (errno.ENOSPC, errno.EDQUOT, errno.EROFS):
        state, detail = 'blocked', 'Storage is full or read-only. Make space or restore write access, then retry.'
    else:
        state, detail = 'error', 'I/O failed. Check storage and retry; the previous verified backup is retained.'
    return {'state': state, 'operation': operation, 'error_code': code, 'detail': detail}
