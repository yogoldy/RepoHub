# Repo Hub

A simple local Mac app showing whether the latest iCloud-folder backups match the repos on Leo's Desktop. A horizontal menu-bar panel, expandable repo details, and an optional full status page with Advanced details. The scoped JSON helper remains available as a foundation for future tools.

## Pieces

- A Python standard-library helper serves only `127.0.0.1:8767`, scans the configured repos every 30 seconds, and backs them up on a configurable schedule while the Mac is awake.
- A native Swift / WKWebView menu-bar app (macOS 13 or later, built for this Mac) opens a transient card panel directly under its menu-bar icon. Clicking outside dismisses it; reopening preserves the selected repo and scroll position. Quitting the menu-bar app does not stop backups.
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

The last-file-change display excludes Git internals, `.DS_Store`, and AppleDouble metadata; those files are still included in backups. The menu bar shows upload progress, pending changes, and the newest snapshot time. “Backup notifications” controls macOS completion and persistent-problem notifications. Permission is requested from macOS; if denied, no notification can be delivered. Notifications require verified hashes and upload acknowledgement for the same exact current archive. Delivered archive/hash receipts are saved in app preferences to prevent duplicate notices across polls/restarts. Multiple completions in one poll share a notification.

Installed configuration sets `retention` to `latest`, `require_upload_before_prune` to true, and `verification_seconds` to 900. Older/custom configurations that omit this field retain all archives until explicitly migrated.

## Independent cloud verification

Upload acknowledgement is not an independent restore audit. On another authenticated computer, download the exact dated archive from iCloud (not a copy transferred from this Mac), then compare its SHA-256 to the saved `sha256` in `backups.json` or `Snapshots/index.json`. Matching hashes prove the retrieved archive bytes match the verified local archive. A restore into a new empty folder can then test usability. No remote verifier or credentials are configured in this release; do not expose backups publicly or place Apple credentials in source code. Codex/cloud environments require separate iCloud authentication and network access; this local app cannot grant that access.

Notification readiness checks: compile `native/BackupReadiness.swift` and `native/ProblemAlerts.swift` with `tests/readiness.swift`, then run the resulting executable.

## Settings, power and health

The top-right gear opens a small settings panel with independent battery and power-adapter policies. Timed backups offer Off, 15 minutes, 30 minutes, 1 hour, 2 hours or 4 hours. After-edits backups are independent of the timed schedule and offer a 2, 5, 10, 15 or 30 minute quiet period per repo. Defaults retain hourly backups on both power sources and disable after-edit backups on both sources. Timed scheduling survives helper restarts and sleep using a persisted wall-clock timestamp. Edit quiet periods restart on newly observed metadata changes and on helper restart; changes are observed at the normal 30-second scan cadence. Changed repos are copied individually along with saved helper data. Failed attempts retry at most every five minutes. Continuous editing still receives the configured timed backup attempt; live-file consistency checks can defer publication if files keep changing.

Settings live in `data/settings.json`, which is included in saved helper-data backups. GET/POST `/api/settings` retains loopback Host, Origin and process-token checks, validates a fixed schema, and requires the saved revision to prevent overwriting concurrent settings changes. Installation preserves existing settings and configuration. Automatic backup starts and the boundary between repos recheck the actual `pmset -g batt` power source. Unknown power pauses automatic copies. A power change lets the archive already in flight finish before pausing the remaining automatic run; macOS controls uploads already queued. Manual Back up now bypasses scheduling and power restrictions.

Green requires fresh observations as well as verified hashes and macOS upload acknowledgement. Default freshness limits are two minutes for repo scans, 45 seconds for upload probes, and 17 minutes for hash checks (15-minute interval plus two-minute grace). Failed/unreachable helper requests clear the dashboard's green marks and disable Back up now until it reconnects. A 20-second browser watchdog catches a hanging request. Stale acknowledgement cannot prune previous archives or trigger completion notifications.

The menu's Backup notifications switch covers completion and problem notices. Persistent copy/upload errors and stale checks wait two minutes before a problem notice. Pending uploads with no observed percentage change for 30 minutes and copies on the same repo for 30 minutes also surface an issue. Moving percentage observations reset the upload wait, including progress accompanied by error 4355. Missing percentage is not proof the transfer stopped: the notice says it has not shown progress. Problem episodes are persisted, reset only after observed recovery, grouped, and deduplicated in native preferences with a 30-minute notification cooldown. Notification display continues to depend on macOS permission and Focus.

## Menu-bar repo cards

The menu-bar icon opens a themed NSPopover with three repo cards visible at once. Horizontal trackpad scrolling, previous/next arrows, and Left/Right/Home/End keyboard navigation reach every repo. Clicking a card expands its backup status below the rail: last archive saved, last hash check, archive size, and observed upload progress when available. Selection and card DOM identity survive five-second updates. New repos appear automatically; removal of the selected repo safely selects another. No Git details appear in this compact panel.

A green card requires fresh checks, no new edits or copy errors, and matching verification/upload observations for the exact current archive. Stale data, source changes, missing archive identities, and 100% pending progress cannot become Backed up. Local archive creation uses indeterminate progress; the app does not invent a copying percentage. A saved copy uploading while newer edits exist remains New edits.

Back up now, Repository Backups, Backup notifications, and the settings gear use the same card theme. Settings open inside the popover and save to the same revision-safe settings API; no full app window is needed. There is no Open Repo Hub menu button. A small Quit control stops only the menu-bar app. The original full dashboard remains available at the helper root for development/Advanced inspection.

The native bridge accepts only openBackups, toggleNotifications, and quit from this popover's exact top-level http://127.0.0.1:8767/menu.html document. Other origins, ports, paths, subframes, extra fields and arbitrary path/command requests are rejected. HTML views never receive this bridge. Backups and settings still go through authenticated loopback POST endpoints, obtaining the current process token for each write so a helper restart does not strand the panel with an old token. Browser-only previews disable the three native controls.

Menu checks: `node tests/menu-status.cjs`; compile `native/MenuBridge.swift` with `tests/menu_bridge_checks.swift` and run the executable. Existing Python security/backup and Swift notification-readiness checks still apply. This branch starts from 9f442b8 and adds the menu-bar presentation, its fixed adapter and per-repo schedules; cloud restore verification remains a separate future pass.

## Individual repo schedules and status icons

The top-right gear edits **default backup settings** only. In the menu bar, select a repo and choose **Schedule** to set that repo's timed frequency, after-edit delay and battery/adapter behavior. **Use default backup settings** restores inheritance, including future default changes. Custom schedules are labelled Custom on the card detail; otherwise Default is shown. The full status page provides defaults only and points to the menu bar for individual adjustments. Manual Back up now still checks all repos, regardless of their schedules.

Overrides are validated and persisted in `data/repo-settings.json` beside the defaults, included in the helper-data archive. Scoped GET/POST `/api/repo-settings/<workspace-id>` accepts only current repo IDs, the fixed policy schema, and both override/default revisions. Origin/token/Host guards remain unchanged. Each repo has its own persisted periodic timestamp so a fast repo cannot reset a slower repo's timer; a power-change pause advances only repos actually attempted.

Drawn SVG icons avoid relying on font glyphs: check = verified and uploaded; clock = waiting for iCloud; pencil = new edits; up arrow = uploading; circular arrow = backing up; magnifying glass = checking hashes; clock with alert = outdated status; warning triangle = needs attention; question mark = unconfirmed. Both views offer **What the status icons mean**, alongside visible per-repo status text. The gear and action icons use the same drawing style. The menu popover is 640 points tall and scrolls when an expanded legend or longer detail needs more space.

Battery settings offer **Automatic backups on battery**. Unchecking it selects manual-only operation on battery and disables its timed/after-edit controls; Back up now still works. This shortcut is offered only for battery, including custom repo schedules. It persists as battery frequency Off plus after-edits Off, using the existing validated policy schema. Turning automatic operation back on starts with hourly timing if the saved frequency is Off. New installations default to no after-edit backups on battery; this requested upgrade turns that off in saved global defaults while preserving frequencies, adapter settings and custom repo policies.
