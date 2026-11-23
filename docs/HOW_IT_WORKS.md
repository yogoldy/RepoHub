# How RepoHub works (technical reference)

This is the detailed reference for what RepoHub does and why. New here? Start with the [README](../README.md) and the [getting started guide](GETTING_STARTED.md).

RepoHub shows whether the latest iCloud-folder backups match your repos. A horizontal menu-bar panel, expandable repo details, and an optional full status page with Advanced details. The scoped JSON helper remains available as a foundation for future tools.

## Product direction

See the [roadmap](../ROADMAP.md) for where the app is headed. Git discovery, readable backup-folder names, continuous diagnostics, constrained exports, explicit GitHub delivery and [native source pickers with reviewed workspace selection](WORKSPACE_CONFIGURATION.md) are implemented.

Releases are signed, notarized and delivered through Sparkle; see [releasing](RELEASING.md). Publishing source does not upload personal backups or diagnostics.

## Pieces

- A Python standard-library helper serves only `127.0.0.1:8767`, scans the configured repos every 30 seconds, and backs them up on a configurable schedule while the Mac is awake.
- A native Swift / WKWebView menu-bar app (macOS 13 or later on Apple silicon) opens a transient card panel directly under its menu-bar icon. Clicking outside dismisses it; reopening preserves the selected repo and scroll position. Quitting the app stops its helper, so no backups run until you open RepoHub again (it also starts at login).
- Workspace-scoped JSON written through the data API is stored in `~/Library/Application Support/RepoHub/data/workspaces/`. The hub stores its current repo status as `status.json` and backup metadata as `backups.json` beside the data folder.
- The menu-bar app starts the helper and restarts it if it exits unexpectedly. After setup the app attempts login registration once if needed. Backups resume at login when macOS enables the item or an existing launch agent starts the app. macOS suspends work during sleep; it resumes when the Mac wakes.

## Backups

The existing repo-home mode monitors immediate folders under a chosen containing folder, including folders without Git. Native source pickers also support individually selected folders at unrelated locations, with exact-path review before saving. Recursive Git discovery is a separate, explicit tool in setup that proposes repos for you to review; it never starts monitoring on its own. Backups include `.git`, uncommitted files, ignored files, dependencies, and empty folders. Symlinks are preserved as links; their outside targets are not copied. The app never changes the source repos.

Changed workspaces replace their current full `.tar.gz` archive with a newly dated copy in the backup folder you chose in iCloud Drive, in a subfolder named after the repo. The helper hashes every regular source file with SHA-256, including ignored files and Git internals. New copies are checked against the decompressed archive's actual file contents, permissions, directories and link targets, and then against a second source-content pass. Destination archive bytes must also pass SHA-256 verification before the indexes are saved.

A deep match check hashes source contents and the stored archive every 15 minutes, during backup attempts and on the first eligible deep scan after startup, and when Refresh is pressed. The trusted archive content digest comes from its actual stored members; older archives are read and verified before obtaining that digest. Ordinary metadata scans detect visible changes every 30 seconds and invalidate prior verification when source metadata or archive identity changes. Each new content pass reads regular-file bytes. Between passes, scans can reuse an unexpired verification receipt while the source metadata fingerprint and archive identity still match. The UI calls this “Hashes verified” and shows the verification time. Hashing still reads and checks real source/archive bytes; the wording does not weaken the verification. These are observations of live files, not atomic filesystem/database snapshots; close active database/workbook writers for a fully consistent restore.

The read-only `native/CloudStatus.swift` adapter queries Apple's Foundation URL resource values and subscribes to published `NSProgress` for the exact archive path. An upload is confirmed only when macOS identifies an iCloud item, explicitly reports `ubiquitousItemIsUploaded`, and does not report an active upload, error or unresolved conflict. A failed probe or insufficient upload evidence produces an unknown backend state. The panel displays “Upload status unavailable” when that state determines the card. Upload status and published percentages refresh about every five seconds, independently of hash verification. Missing progress produces an indeterminate bar, not a made-up percentage. A percentage, including 100%, never confirms an upload. When macOS simultaneously reports uploading and error 4355, the row remains Uploading and preserves the reported error in Advanced rather than calling the upload blocked. Conflicts remain errors. This is macOS's upload acknowledgement, not an independent server-side download/checksum audit. See [Apple's upload-confirmation guidance](https://developer.apple.com/library/archive/documentation/General/Conceptual/iCloudDesignGuide/Chapters/TestingandDebuggingforiCloud.html) and [upload resource key](https://developer.apple.com/documentation/foundation/urlresourcekey/ubiquitousitemisuploadedkey).

Only the current managed archive is retained after the in-memory current record identifies a verified replacement set and fresh macOS observations confirm its upload. A prior index write may still need repair. The previous copy remains while the new one is uploading, unknown or in error; temporary duplicate archives are intentional during this period. A failed index write stops cleanup in that backup attempt. A later upload poll can still prune an older archive using the in-memory replacement record before the failed index write is repaired. Cleanup is confined to managed archive names inside workspace snapshot folders and rejects stale observations of superseded archives. Existing legacy backups and saved JSON revision history are preserved.

The saved helper JSON also gets a current archive in a `.repohub-data` folder in the backup folder, with its upload state checked separately. Ordinary repos carry their committed history in `.git`; replacing backups loses older uncommitted/ignored-file versions. Symlink targets outside the repo, including external Git worktree metadata, are not copied.


## Status and retained helper API

The default Repos view is a simple list with a checkmark, live per-archive upload bar/percentage, pending/issue status, and verification time. Advanced is off by default and reveals Git branch, staged/unstaged/untracked file counts, last file modification, and archive details. A green checkmark requires both verified hashes and explicit upload confirmation. Red indicates a copy/upload issue; amber indicates a pending check or upload. Upload status is shown separately, so a valid local copy can still be waiting for iCloud. It does not mean the working tree equals a Git commit.

The sidebar and Repo views screen have been removed. Existing saved JSON and the scoped JSON/view endpoints remain intact for future integrations; the status page does not expose view registration or a notes editor.

HTTP writes require an exact loopback Host, same Origin, and a per-process token. There is no arbitrary filesystem-write endpoint or public listener. View asset paths resolve inside their repo, including symlink checks; the resolved target must stay inside the repo and have an allowed extension, and the requested path must have no dot-prefixed component.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
python3 repohub.py --config /path/to/config.json
```

Install RepoHub from a GitHub release. `tools/package_app.py` declares which Python modules ship in the app (`RUNTIME_MODULES`). Tests use temporary synthetic repos and a temporary HTTP server. They verify archive contents, symlinks, changing-source rejection, unchanged skip, verified replacement and cleanup failure recovery, JSON persistence/conflicts/revisions, request origin and Host checks, view traversal boundaries, and JSON-data backup.

To restore, list an archive with `tar -tzf SNAPSHOT.tar.gz`, then extract it into a new empty folder outside the active repos. Do not overwrite an active repo or Office workbook during restoration.

The last-file-change display excludes Git internals, `.DS_Store`, and AppleDouble metadata; those files are still included in backups. The menu-bar item shows the selected count or an activity or warning symbol. Open a repo card for its archive creation time and available upload progress. “Backup notifications” controls macOS completion and persistent-problem notifications. Permission is requested from macOS; if denied, no notification can be delivered. Completion notifications require a fresh hash match and upload acknowledgement for the same current archive. Problem notifications use separate failure and persistence checks. Delivered archive/hash receipts are saved in app preferences to prevent duplicate notices across polls/restarts. Multiple completions in one poll share a notification.

Installed configuration sets `retention` to `latest` and `verification_seconds` to 900. Under latest-only retention, a previous archive is deleted only after its replacement is verified and macOS confirms the replacement uploaded; this safeguard is always on and cannot be turned off by configuration. Configurations that omit `retention` keep all archives.

## Independent cloud verification

Upload acknowledgement is not an independent restore audit. On another authenticated computer, download the exact dated archive from iCloud (not a copy transferred from this Mac), then compare its SHA-256 to the saved `sha256` in `backups.json` or the `index.json` file in the backup folder. Matching hashes prove the retrieved archive bytes match the verified local archive. A restore into a new empty folder can then test usability. No remote verifier or credentials are configured in this release; do not expose backups publicly or place Apple credentials in source code. Direct retrieval from iCloud requires separate access. A receiving environment can verify privately supplied files offline without iCloud credentials; this local app cannot grant that access.

Notification readiness checks: compile `native/BackupReadiness.swift` and `native/ProblemAlerts.swift` with `tests/readiness.swift`, then run the resulting executable.

## Settings, power and health

The top-right gear opens a small settings panel with independent battery and power-adapter policies. Timed backups offer Off, 15 minutes, 30 minutes, 1 hour, 2 hours or 4 hours. After-edits backups are independent of the timed schedule and offer a 2, 5, 10, 15 or 30 minute quiet period per repo. Defaults retain hourly backups on both power sources and disable after-edit backups on both sources. Timed scheduling survives helper restarts and sleep using a persisted wall-clock timestamp. Edit quiet periods restart on meaningful file/Git metadata changes and on helper restart; Finder view-state writes and directory timestamp/size churn do not restart them; changes are observed at the normal 30-second scan cadence. Changed repos are copied individually along with saved helper data. Failed attempts retry at most every five minutes. Continuous editing still receives the configured timed backup attempt; live-file consistency checks can defer publication if files keep changing.

Settings live in `data/settings.json`, which is included in saved helper-data backups. GET `/api/settings` checks the loopback Host. POST also checks Origin and the process token, validates a fixed schema, and requires the saved revision to prevent overwriting concurrent settings changes. Installation preserves existing settings and configuration. Automatic backup starts and the boundary between repos recheck the actual `pmset -g batt` power source. Unknown power pauses automatic copies. A power change lets the archive already in flight finish before pausing the remaining automatic run; macOS controls uploads already queued. Manual Back up now bypasses scheduling and power restrictions.

Green requires fresh observations as well as verified hashes and macOS upload acknowledgement. Default freshness limits are two minutes for repo scans, 45 seconds for upload probes, and 17 minutes for hash checks (15-minute interval plus two-minute grace). Failed/unreachable helper requests clear the dashboard's green marks and disable Back up now until it reconnects. Dashboard requests time out after eight seconds. A separate five-second timer marks the displayed status stale once its last successful response is over 20 seconds old. Stale acknowledgement cannot prune previous archives or trigger completion notifications.

The menu's Backup notifications switch covers completion and problem notices. Persistent copy and upload errors normally become eligible after two minutes. Scan-only staleness can wait ten minutes during a progressing full scan, and the notification cooldown still applies. Pending uploads with no observed percentage change for 30 minutes and copies on the same repo for 30 minutes also surface an issue. Moving percentage observations reset the upload wait, including progress accompanied by error 4355. Missing percentage is not proof the transfer stopped: the notice says it has not shown progress. Problem episodes are persisted, retired when absent from the current observations and restarted when their marker or detail changes, grouped, and deduplicated in native preferences with a 30-minute notification cooldown. Notification display continues to depend on macOS permission and Focus.

## Menu-bar repo cards

The menu-bar icon opens a themed NSPopover with three repo cards visible at once. Horizontal trackpad scrolling, previous/next arrows, and Left/Right/Home/End keyboard navigation reach every repo. Clicking a card expands its backup status below the rail: last archive saved, last hash check, archive size, and observed upload progress when available. Selection and card DOM identity survive five-second updates. New repos appear automatically; removal of the selected repo clears the selection and returns the panel to the overview. The compact panel can identify Git-only changes. Branch names and staged, unstaged and untracked counts appear in the full dashboard’s Advanced view.

A green card requires fresh checks, no content differences (other than Finder's `.DS_Store` view settings) or copy errors, and matching verification/upload observations for the exact current archive. Stale data, source changes, missing archive identities, and 100% pending progress cannot become Backed up. Local archive creation uses indeterminate progress; the app does not invent a copying percentage. A repo with confirmed newer project files stays “Edits confirmed” while its saved copy uploads.

Back up now, Repository Backups, Backup notifications, and the settings gear use the same card theme. Settings open inside the popover and save to the same revision-safe settings API; no full app window is needed. There is no Open Repo Hub menu button. A small Quit control stops the menu-bar app and its backup helper; backups resume when RepoHub is opened again. The original full dashboard remains available at the helper root for development/Advanced inspection.

The native bridge accepts only a fixed set of actions (notification, privacy and login settings, opening the backup folder or a repo in Finder, toggling notifications, connecting GitHub, the setup folder and destination pickers, update checks, update channel and menu-appearance preferences, and quit) from a top-level panel document with scheme `http`, host `127.0.0.1`, the expected port and path `/menu.html`, or from the setup page for the setup actions. Other origins, ports, paths, subframes, extra fields and arbitrary path/command requests are rejected. openRepo accepts only a workspace ID and resolves its path from fresh helper status and the registry's exact approved ID/path pair, requiring an existing canonical non-symlink directory. Older single-root helper status retains its immediate-child check. HTML views never receive this bridge. Backups and settings still go through authenticated loopback POST endpoints, obtaining the current process token for each write so a helper restart does not strand the panel with an old token. Browser-only previews disable the three native controls.

Menu checks: `node tests/menu-status.cjs`; compile `native/MenuBridge.swift` and `native/MenuAppearance.swift` with `tests/menu_bridge_checks.swift` and run the executable. Existing Python security/backup and Swift notification-readiness checks still apply. Validation of other Finder sync folders is on the [roadmap](../ROADMAP.md).

Settings → **Menu bar appearance** chooses what the number counts: repos waiting
for backup, repos with confirmed changes, or no number. The default remains waiting
for backup. Counts aggregate the same statuses as the repo cards; Finder-only
Backed up does not become pending or upload-unconfirmed. Confirmed changes excludes
first backups and comparisons that still need verification. A zero number is
hidden, and activity/warning symbols remain available. Save changes stores this
preference separately on each Mac without changing backup settings or schedules.

## Individual repo schedules and status icons

The gear opens Settings. Its **Backup schedule** page edits the defaults. In the menu bar, select a repo and open the timing row in its details, labelled with its current schedule to set that repo's timed frequency, after-edit delay and battery/adapter behavior. **Use default backup settings** restores inheritance, including future default changes. Custom schedules are labelled Custom on the card detail; otherwise Default is shown. The full status page provides defaults only and points to the menu bar for individual adjustments. Back up now and Rescan now act on the repo expanded in the panel, or on the repos you choose in the overview chooser, regardless of their schedules.

Overrides are validated and persisted in `data/repo-settings.json` beside the defaults, included in the helper-data archive. GET `/api/repo-settings/<workspace-id>` returns the policy and both revisions for a current repo. POST requires both revisions and either a valid policy or null to restore inheritance. Origin/token/Host guards remain unchanged. Each repo has its own persisted periodic timestamp so a fast repo cannot reset a slower repo's timer; a power-change pause advances only repos actually attempted.

Status icons are drawn as SVG rather than font glyphs. The panel’s **Backup information → What your backup status means** page explains the six categories (Backed up, a backup is waiting to run, working, upload not yet confirmed, waiting for fresh checks, needs attention), and the [getting started guide](GETTING_STARTED.md#reading-the-panel) summarizes them.

Battery settings offer **Automatic backups on battery**. Unchecking it selects manual-only operation on battery and disables its timed/after-edit controls; Back up now still works. This shortcut is offered only for battery, including custom repo schedules. It persists as battery frequency Off plus after-edits Off, using the existing validated policy schema. Turning automatic operation back on starts with hourly timing if the saved frequency is Off. New installations default to no after-edit backups on battery; existing installations keep their saved global defaults and per-repo policies.

Each card's folder icon is a separate **Open [repo] in Finder** button. Clicking the rest of the card selects its status. **Things to know**, available from **Backup information** in the panel and below the status guide on the full dashboard, explains the Finder shortcut, default versus custom schedules, and what backups include. Browser-only previews disable Finder buttons. Folder openings use the exact menu-page bridge and never accept a user-supplied path or URL.

**Show me** in Things to know briefly enlarges, shakes and highlights the selected repo's actual folder button, scrolling it into view when needed. It does not open Finder or change the selected repo. Reduced Motion uses a still enlargement/highlight. The full dashboard illustrates the same folder symbol inline because its Finder controls are in the native menu bar.

Expanded Things to know uses a separate spaced block: extra space after the Finder demonstration row, between each explanatory line, and before the action buttons/footer text. The menu uses a separate information page with padded sections. The full dashboard uses a collapsible block with spacing between its rows.

Change detection compares full content hashes, paths, permissions and symlink targets. Timestamp-only differences do not request a replacement archive after verification. Finder metadata (`.DS_Store` / AppleDouble `._` files) and Git data are disclosed separately from repo files; all remain included in backups. The latest file timestamp in Advanced is informational, not proof of a user edit. Advanced lists up to eight observed differences against the saved archive.

## Local diagnostics

The helper writes structured events under `~/Library/Application Support/RepoHub/diagnostics/` while it runs, including startup and a heartbeat on eligible scheduler ticks, at most once per minute. Logging continues with the menu panel closed. Gaps longer than two minutes between heartbeat calls in the same helper process are recorded as unobserved intervals; sleep/offline time is not falsely presented as monitored. Files rotate at 10 MiB, with seven-day/100 MiB total retention, owner-only permissions and recovery from failed/partial writes. Diagnostic files are outside monitored repos and helper-data archives. The status API reports recording failures without interrupting backups. Reports remain local until an explicit Send posts the exact preview to GitHub. Diagnostic export is constrained by the typed sharing contract; no background telemetry is enabled.


Scan events capture signature transitions, hash freshness, duration and counts of Finder metadata, Git data and repo-file differences. Repo/path references are hashed identifiers; events exclude raw repo names, file contents, exception prose and credentials. When a view is rendered, the native menu and full dashboard report their actual label and readiness against the same backend observation ID. Recording failures never change backup decisions, and missing view receipts never establish agreement.

Read a local diagnostic summary with:

```sh
python3 diagnostics_report.py --log-dir "$HOME/Library/Application Support/RepoHub/diagnostics"
```

The reader skips malformed records and unsafe file types. An optional `--output` writes a new owner-only JSON file and refuses to overwrite an existing one. These summaries are local investigation tools; [constrained sharing bundles](DIAGNOSTIC_EXPORT.md) and [explicit GitHub delivery](REPORT_DELIVERY.md) are separate reviewed flows. Manually saved case reports live separately from the automatic seven-day log retention.


## Finder-only changes and repo-scoped replacements

Ordinary `.DS_Store` file additions, deletions and content changes do not trigger replacement archives or after-edit timers by themselves. The helper still hashes every source file and verifies the existing archive checksum. Full verification stays `different` when Finder bytes differ; a separate `ignored_finder_only` receipt explains why `needs_backup` is false. With a fresh verification and a confirmed upload of the same archive, the card shows the normal green **Backed up**, and its technical details say that only Finder view settings differ. Freshness and upload checks still apply.

This exception applies only to regular files named `.DS_Store`. Symlinks/directories at that name, AppleDouble `._` files, ignored/hidden files and Git data other than regular `.DS_Store` files still trigger replacement when changed. A new archive caused by meaningful changes includes the current `.DS_Store` files too. Timestamp-only changes continue to reuse the existing verified copy. Missing or corrupt copies still need replacement.

Scheduled and manual checks may inspect all repos. They create archives only for the repos that need replacements; a targeted after-edit backup cannot create another repo's archive. Explicit selections must use current workspace IDs. The shared iCloud index is written only when its data changes or a failed publication needs recovery, so successful unchanged checks do not repeatedly upload identical index data. Saved app data remains a separately verified backup. macOS controls transfer timing; Repo Hub decides which new archives to publish.


Lifecycle diagnostics record scheduling/power decisions, quiet-period/retry waits, backup stages, failures and restart interruptions. New archives carry their creating run ID; upload and cleanup events identify that exact archive. Unchanged observations are recorded at most once per minute. Icon receipts include their decision explanation and run/archive links, with backend-input disagreements separated from cross-view disagreements. These are diagnostic checks, not a replacement for hash verification or independent restore testing. The local report retains the latest 200 lifecycle events; it is not a sanitized sharing bundle.


## Public repository and private inputs

GitHub hosts the app source at https://github.com/yogoldy/RepoHub. Environment values, credential/signing files, runtime state, raw diagnostic logs and backup/restore archives are covered by `.gitignore` when their names or locations match its patterns. Example environment files may be tracked only with placeholders. Ignore rules do not remove already tracked files or secrets from history, so review staged changes before pushing.

Keep restore inputs outside the repository, or in the ignored `restore-inputs/` directory. Transfer backup archives privately to the verification host. Any future transfer to a cloud test environment is separate from publishing source and needs an explicitly chosen private transfer route. Git ignore rules do not change RepoHub backup coverage: ignored files, including local environment files, remain part of full backups.


## Independent restore audit

See [CLOUD_RESTORE_HANDOFF.md](CLOUD_RESTORE_HANDOFF.md) for the independent restore procedure and its required private inputs. `restore_audit.py` independently captures source expectations and verifies the supplied archive in a fresh output directory, including Git checks and structured logs. No iCloud credentials or restored-code execution are needed. Actual archives/baselines remain private; successful synthetic tests are not proof that a particular iCloud archive can be restored.

## Golden-rule release checks

Run `python3 tools/release_gate.py --require-clean` on clean macOS source before promotion. [The release contract](quality/RELEASE_GATE.md) explains the executable checks and remaining manual obligations; [the failure-mode register](quality/FAILURE_MODES.md) connects diagnostic evidence, fixes, susceptible boundaries and exact regression tests. GitHub runs the automated gate for pushes to `main`, pull requests and manual dispatches.

GitHub bug/feature delivery, native credential setup and uncertain-send recovery are described in [the delivery contract](REPORT_DELIVERY.md).
