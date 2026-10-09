# Repo Hub

A local Mac foundation for HTML views across Leo's repos. Repo status and backups are the first modules; the shared JSON helper supports future repo-specific views.

## Pieces

- A Python standard-library helper serves only `127.0.0.1:8767`, scans the configured repos every 30 seconds, and backs them up hourly while the Mac is awake.
- A native Swift / WKWebView menu-bar app (macOS 13 or later, built for this Mac) opens the HTML dashboard. Closing its window leaves the helper running. Quitting the menu-bar app does not stop backups.
- Each workspace has persistent JSON files in `~/Library/Application Support/RepoHub/data/workspaces/`. The hub stores its current repo status as `status.json` and backup metadata as `backups.json` beside the data folder.
- Independent login LaunchAgents start the helper and menu-bar app. macOS suspends work during sleep; it resumes when the Mac wakes. KeepAlive restarts the helper after an unexpected exit.

## Backups

Every folder immediately under `~/Desktop/repos` is a workspace, including folders without Git. Backups include `.git`, uncommitted files, ignored files, dependencies, and empty folders. Symlinks are preserved as links; their outside targets are not copied. The app never changes the source repos.

Changed workspaces get dated full `.tar.gz` archives in `iCloud Drive/Repository Backups/Snapshots/<workspace-id>/`. The helper compares path, size, mode, symlink target, and nanosecond modification time to skip unchanged workspaces. A file changed while deliberately retaining all those metadata values will not trigger a new backup. The helper verifies the archive SHA-256 after publication and rejects a snapshot if source metadata changes during its creation. This is a checked live-file copy, not an atomic filesystem or database snapshot; close active database/workbook writers for a fully consistent restore.

The saved view JSON, registry, and prior JSON revisions also receive a full snapshot under `Snapshots/repohub-data/`. No old archives or JSON revisions are automatically deleted. Full archives of frequently changing large repos can consume substantial iCloud space. Archive verification confirms local bytes; macOS separately uploads them to iCloud. The UI does not claim upload completion.

Installation preserves the previous mirror under `Repository Backups/Legacy Current repos` and all `Desktop repos Previous Versions` history. It disables the old hourly job that wrote to `iCloud Drive/Desktop/repos`, changes that old script's destination to the preserved mirror location, and replaces its schedule with the hub. The obsolete cloud Desktop folder goes to the Mac's Trash after the repo mirror is preserved. Local Desktop is unaffected.

## HTML view contract

The default Repos view is a simple list with a checkmark, pending/issue status, and snapshot time. Advanced is off by default and reveals Git branch, staged/unstaged/untracked file counts, last file modification, and archive details. A checkmark compares the current source metadata with the last verified snapshot, checks that the archive still exists, and includes all uncommitted files; it does not mean the working tree equals a Git commit or that iCloud upload has completed.

Register an existing `.html` file using Repo views → Add an HTML view. Paths are relative to the chosen repo. The hub injects `view-client.js`; original files remain unchanged. Use relative local asset paths. Current assets support HTML, JS, CSS, images and web fonts. Remote network calls and nested frames are blocked.

```js
const saved = await RepoHub.getJSON('project-settings'); // null on first load
await RepoHub.saveJSON('project-settings', { theme: 'light' });
```

Load a named JSON before saving it. Saves compare its revision and reject conflicting edits; successful replacements preserve the previous JSON. Names use letters, digits, hyphens and underscores. JSON is stored in the app's workspace folder, not added to source repos. Repo writes or other folder access would require a separately scoped adapter.

HTML views run in opaque-origin sandboxed iframes. The trusted shell brokers JSON requests only for the selected workspace. HTTP writes require an exact loopback Host, same Origin, and a per-process token. There is no arbitrary filesystem-write endpoint or public listener. View asset paths resolve inside their repo, including symlink checks; hidden paths and unsupported file types are blocked.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
python3 repohub.py --config /path/to/config.json
```

See `install.py` for installed paths and migration. Tests use temporary synthetic repos and a temporary HTTP server. They verify archive contents, symlinks, changing-source rejection, unchanged skip, retained snapshots, JSON persistence/conflicts/revisions, request origin and Host checks, view traversal boundaries, and JSON-data backup.

To restore, list an archive with `tar -tzf SNAPSHOT.tar.gz`, then extract it into a new empty folder outside the active repos. Do not overwrite an active repo or Office workbook during restoration.

The last-file-change display excludes Git internals, `.DS_Store`, and AppleDouble metadata; those files are still included in backups. The menu bar shows backup progress, pending changes, and the newest snapshot time.
