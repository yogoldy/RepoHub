# Repo Hub

A simple local Mac app showing whether the latest iCloud-folder backups match the repos on Leo's Desktop. One status page, an optional Advanced toggle, and a menu-bar item. The scoped JSON helper remains available as a foundation for future tools.

## Pieces

- A Python standard-library helper serves only `127.0.0.1:8767`, scans the configured repos every 30 seconds, and backs them up hourly while the Mac is awake.
- A native Swift / WKWebView menu-bar app (macOS 13 or later, built for this Mac) opens the HTML dashboard. Closing its window leaves the helper running. Quitting the menu-bar app does not stop backups.
- Each workspace has persistent JSON files in `~/Library/Application Support/RepoHub/data/workspaces/`. The hub stores its current repo status as `status.json` and backup metadata as `backups.json` beside the data folder.
- Independent login LaunchAgents start the helper and menu-bar app. macOS suspends work during sleep; it resumes when the Mac wakes. KeepAlive restarts the helper after an unexpected exit.

## Backups

Every folder immediately under `~/Desktop/repos` is a workspace, including folders without Git. Backups include `.git`, uncommitted files, ignored files, dependencies, and empty folders. Symlinks are preserved as links; their outside targets are not copied. The app never changes the source repos.

Changed workspaces replace their current full `.tar.gz` archive with a newly dated copy in `iCloud Drive/Repository Backups/Snapshots/<workspace-id>/`. The helper hashes every regular source file with SHA-256, including ignored files and Git internals. New copies are checked against the decompressed archive's actual file contents, permissions, directories and link targets, and then against a second source-content pass. Destination archive bytes must also pass SHA-256 verification before the indexes are saved.

A deep match check hashes source contents and the stored archive every 15 minutes, at startup/backup time, and when Refresh is pressed. The trusted archive content digest comes from its actual stored members; older archives are read and verified before obtaining that digest. Ordinary metadata scans detect visible changes every 30 seconds and invalidate prior verification when source metadata or archive identity changes. Source digests are never reused just because sizes or timestamps match. The UI calls this “Hashes verified” and shows the verification time. Hashing still reads and checks real source/archive bytes; the wording does not weaken the verification. These are observations of live files, not atomic filesystem/database snapshots; close active database/workbook writers for a fully consistent restore.

The read-only `native/CloudStatus.swift` adapter queries Apple's Foundation URL resource values and subscribes to published `NSProgress` for the exact archive path. An upload is confirmed only when macOS identifies an iCloud item, explicitly reports `ubiquitousItemIsUploaded`, and does not report an active upload, error or unresolved conflict. Missing values, unavailable APIs, and failed probes are shown as Unknown. Upload status and published percentages refresh about every five seconds, independently of hash verification. Missing progress produces an indeterminate bar, not a made-up percentage. A percentage, including 100%, never confirms an upload. When macOS simultaneously reports uploading and error 4355, the row remains Uploading and preserves the reported error in Advanced rather than calling the upload blocked. Conflicts remain errors. This is macOS's upload acknowledgement, not an independent server-side download/checksum audit. See [Apple's upload-confirmation guidance](https://developer.apple.com/library/archive/documentation/General/Conceptual/iCloudDesignGuide/Chapters/TestingandDebuggingforiCloud.html) and [upload resource key](https://developer.apple.com/documentation/foundation/urlresourcekey/ubiquitousitemisuploadedkey).

Only the current managed archive is retained once its replacement is verified, indexed, and confirmed uploaded. The previous copy remains while the new one is uploading, unknown or in error; temporary duplicate archives are intentional during this period. Failed replacement, checksum or index publication preserves older copies. Cleanup is confined to managed archive names inside workspace snapshot folders and rejects stale observations of superseded archives. Existing legacy backups and saved JSON revision history are preserved.

The saved helper JSON also gets a current archive under `Snapshots/repohub-data/`, with its upload state checked separately. Ordinary repos carry their committed history in `.git`; replacing backups loses older uncommitted/ignored-file versions. Symlink targets outside the repo, including external Git worktree metadata, are not copied.

Installation preserves the previous mirror under `Repository Backups/Legacy Current repos` and all `Desktop repos Previous Versions` history. It disables the old hourly job that wrote to `iCloud Drive/Desktop/repos`, changes that old script's destination to the preserved mirror location, and replaces its schedule with the hub. The obsolete cloud Desktop folder goes to the Mac's Trash after the repo mirror is preserved. Local Desktop is unaffected.

## Status and retained helper API

The default Repos view is a simple list with a checkmark, live per-archive upload bar/percentage, pending/issue status, and verification time. Advanced is off by default and reveals Git branch, staged/unstaged/untracked file counts, last file modification, and archive details. A green checkmark requires both verified hashes and explicit upload confirmation. Red indicates a copy/upload issue; amber indicates a pending check or upload. Upload status is shown separately, so a valid local copy can still be waiting for iCloud. It does not mean the working tree equals a Git commit.

The sidebar and Repo views screen have been removed. Existing saved JSON and the scoped JSON/view endpoints remain intact for future integrations; the status page does not expose view registration or a notes editor.

HTTP writes require an exact loopback Host, same Origin, and a per-process token. There is no arbitrary filesystem-write endpoint or public listener. View asset paths resolve inside their repo, including symlink checks; hidden paths and unsupported file types are blocked.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
python3 repohub.py --config /path/to/config.json
```

See `install.py` for installed paths and migration. Tests use temporary synthetic repos and a temporary HTTP server. They verify archive contents, symlinks, changing-source rejection, unchanged skip, verified replacement and cleanup failure recovery, JSON persistence/conflicts/revisions, request origin and Host checks, view traversal boundaries, and JSON-data backup.

To restore, list an archive with `tar -tzf SNAPSHOT.tar.gz`, then extract it into a new empty folder outside the active repos. Do not overwrite an active repo or Office workbook during restoration.

The last-file-change display excludes Git internals, `.DS_Store`, and AppleDouble metadata; those files are still included in backups. The menu bar shows upload progress, pending changes, and the newest snapshot time. “Notify when backups are ready” controls macOS completion notifications. Permission is requested from macOS; if denied, no notification can be delivered. Notifications require verified hashes and upload acknowledgement for the same exact current archive. Delivered archive/hash receipts are saved in app preferences to prevent duplicate notices across polls/restarts. Multiple completions in one poll share a notification.

Installed configuration sets `retention` to `latest`, `require_upload_before_prune` to true, and `verification_seconds` to 900. Older/custom configurations that omit this field retain all archives until explicitly migrated.

## Independent cloud verification

Upload acknowledgement is not an independent restore audit. On another authenticated computer, download the exact dated archive from iCloud (not a copy transferred from this Mac), then compare its SHA-256 to the saved `sha256` in `backups.json` or `Snapshots/index.json`. Matching hashes prove the retrieved archive bytes match the verified local archive. A restore into a new empty folder can then test usability. No remote verifier or credentials are configured in this release; do not expose backups publicly or place Apple credentials in source code. Codex/cloud environments require separate iCloud authentication and network access; this local app cannot grant that access.

Notification readiness checks: compile `native/BackupReadiness.swift` with `tests/readiness.swift`, then run the resulting executable.
