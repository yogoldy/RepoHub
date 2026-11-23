"""One explicitly chosen iCloud destination, bound to physical storage identity."""
import errno
from pathlib import Path
import shutil

from access_checks import probe_destination
from workspace_registry import overlaps, source_identity


def icloud_root():
    return Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs'


def inspect_destination(raw, sources, state, *, expected=None, cloud_root=None, required_bytes=0):
    if not isinstance(raw, str) or not Path(raw).is_absolute() or '\x00' in raw:
        raise ValueError('Choose an iCloud Drive folder')
    destination = Path(raw).resolve(strict=True)
    cloud = Path(cloud_root or icloud_root()).resolve(strict=True)
    if destination != cloud and cloud not in destination.parents:
        raise ValueError('Choose a folder inside iCloud Drive for this release')
    if any(overlaps(destination, Path(path)) for path in [*sources, state]):
        raise ValueError('The backup destination must be separate from sources and app state')
    identity = source_identity(destination)
    if expected is not None and expected != identity:
        raise OSError(errno.ESTALE, 'Destination identity changed. Review the destination again.')
    probe_destination(destination)
    free = shutil.disk_usage(destination).free
    required = max(16 * 1024 * 1024, required_bytes)
    if free < required:
        raise OSError(errno.ENOSPC, 'Not enough free space for the selected backup')
    return {'path': str(destination), 'identity': identity, 'free_bytes': free,
            'required_bytes': required, 'provider': 'icloud'}


def require_destination(record):
    """Revalidate without creating a missing directory or changing the saved binding."""
    path = Path(record['path'])
    if path.resolve() != path or source_identity(path) != record['identity']:
        raise OSError(errno.ESTALE, 'Backup destination changed. Review setup before continuing.')
    return path
