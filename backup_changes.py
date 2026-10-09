"""Backup triggers may ignore ordinary Finder view-state files, never repo data."""
from pathlib import Path
import stat


def finder_view_file(relative, item):
    return Path(relative).name == ".DS_Store" and item is not None and item.get("kind") == "file"


def finder_only_difference(source, saved):
    changed = [key for key in source.keys() | saved.keys() if source.get(key) != saved.get(key)]
    return bool(changed) and all(
        all(item is None or finder_view_file(key, item) for item in (source.get(key), saved.get(key)))
        for key in changed)


def edit_entries(entries):
    """Quiet-period hints only. Full content hashes still decide whether to copy."""
    result = []
    for relative, mode, size, mtime, link in entries:
        if Path(relative).name == ".DS_Store" and stat.S_ISREG(mode):
            continue
        # Directory timestamps/sizes change when Finder writes a .DS_Store.
        result.append((relative, mode, 0 if stat.S_ISDIR(mode) else size,
                       0 if stat.S_ISDIR(mode) else mtime, link))
    return result
