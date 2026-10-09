# Verification — 2026-10-09

## Earlier integrity-check checkpoint

- Nineteen synthetic tests pass. Content checks detect equal-size edits with restored modification timestamps, reject content changes during copying, compare actual archived members including hardlinks/empty directories, and detect/repair corrupted archives. Retention tests cover copy/index failures, stale observations, and waiting for upload confirmation. Existing JSON, path, Host/Origin, Git and backup-content tests pass.
- Both native Swift executables compiled for arm64-apple-macos13.0. JavaScript syntax check passed. The installed app displays separate content verification and per-archive upload status; green requires both checks.
- The live full content audit verified all eleven repo copies. macOS reported three uploaded repo archives and eight repo upload errors, plus a saved-data upload error. Every affected upload reports NSCocoaErrorDomain 4355 (iCloud server connection unavailable). Read-only quota check reported 1,600,548,539,775 bytes remaining. Apple's live status page listed iCloud Drive and account sign-in as available at 1:29 PM Eastern. Those observations rule out exhausted storage and a reported general outage; they do not identify the exact connection/session cause.
- A real RepoHub archive was restored into a temporary folder with native tar. All 138 entries matched file bytes, modes and structure, and restored Git passed `git fsck --full`. The temporary restored copy was removed.
- The upload helper successfully reads Apple's documented per-file status keys outside the tool sandbox. Missing flags, failed helpers and conflicts cannot become Uploaded. The helper reports error codes without dumping account identifiers or error userInfo.

## Behavior and deliberate limits

Deep content checks run every 15 minutes, at startup/backup time, and on Refresh; normal metadata and upload checks run every 30 seconds. The displayed verification time identifies the last observation. New archives are decompressed and compared to before/after source content hashes, and destination archive bytes are checksum verified. Existing verified archive content digests can be reused only alongside a fresh source-content hash and a fresh archive checksum.

The prior archive is kept until the replacement is verified, indexed and explicitly confirmed uploaded. Legacy backups and saved JSON are preserved. The iCloud connection issue remains unresolved: no Apple Account, network, sync settings or daemon resets were performed. No logout/reboot or menu-bar dropdown UI inspection was done. Upload confirmation is macOS acknowledgement, not an independently redownloaded server copy. Live copies are not atomic database/filesystem snapshots. Source repos other than RepoHub were not edited or committed.

## Live progress checkpoint — 2026-10-09

- Twenty-one Python tests pass, including progress updates/failure invalidation, non-finite/out-of-range percentage rejection, concurrent upload/error handling, and refusing cleanup at 100% without acknowledgement. Eight Swift notification-readiness checks pass: only the exact current verified/uploaded archive is eligible, repeated receipts are suppressed, pending/100% progress and stale archive signals cannot notify.
- Both Swift binaries compile for arm64-apple-macos13.0, with UserNotifications linked for the native app. JavaScript syntax passes. Published NSProgress observed real archive percentages on this Mac, including WebApp advancing from about 60% to 82%; several other archives report about 99% while acknowledgement is pending.
- Finder/script diagnostics showed identical pending/uploading flags and 4355 errors while Finder bytes and cloudd upload bandwidth kept advancing. Therefore 4355 alongside an active upload does not establish that transfers are blocked. The new app preserves that error in Advanced, shows live upload progress, and continues to reserve green/completion notifications for verified hashes plus macOS acknowledgement.
- Upload/helper/menu/page polling is about five seconds. Hash verification remains every fifteen minutes or Refresh, with all ignored/uncommitted files included. Progress percentages are observed, not estimated. No independent remote download audit has been run; authenticated cloud access must be configured separately. Account/network/sync settings remain unchanged.

Installed observations: all eleven previously pending/current archive upload flags became Uploaded without an iCloud reset. macOS notification permission was initially Denied; the user-requested Repo Hub notification switch was enabled in System Settings and the app now observes Allowed. Completion requests were accepted and archive/hash receipts persisted in preferences. Notification delivery display can still depend on Focus/system presentation settings; no independent cloud download was performed.


## Settings and health branch — 2026-10-09

Implemented on a separate worktree/branch, `codex/backup-settings-health`, from stable main `22fa051`. Main is not edited or merged. New scheduling/power and freshness/problem policies are separate modules; full-file archive checks and latest-only retention remain in place.

- Forty-two Python tests pass, including prior archive/persistence/security checks and new per-repo edit timers, independent power-source policies, unknown-power pause, retry throttling, persisted schedule cadence, revision-safe settings writes, source recheck, stale receipts preserving previous backups, fresh-status expiration and persistent-problem recovery/progress handling.
- Fifteen Swift readiness/problem checks pass. Stale/missing health cannot notify completion; stale/incorrect archives and 100% pending progress remain ineligible. Problem episodes deduplicate and observe the cooldown. Native app compiles for arm64 macOS 13 with AppKit, WebKit and UserNotifications. JavaScript syntax passes.
- An isolated synthetic preview showed the gear panel, independent frequency/delay controls, disabled delay when after-edits is off, saving and reload persistence. Forcing stale repo timestamps removed the green checkmark and showed Status outdated. Browser console contained no errors. Tests do not require changing this Mac's physical power source or account settings.
- No independent iCloud redownload or restore audit was performed in this branch. Notification policy is exercised synthetically; sustained real upload failures and prolonged copy stalls were not deliberately induced on personal backups.

Installed branch observations: the native app opens the top-right gear panel, detects power-adapter operation, and saves the requested defaults: hourly on both sources; after-edits enabled only on battery with a five-minute delay. Existing notification permission remains Allowed. The prior stable app/runtime/configuration is retained locally at `~/Library/Application Support/RepoHub/releases/stable-22fa051`. Upgrade changed only Repo Hub runtime/app files and restarted its own login jobs; no cloud Desktop migration, source-repo edits, account changes or merge into main occurred.


## Horizontal menu-bar branch — 2026-10-09

Branch `codex/menu-bar-repo-cards` starts exactly from `9f442b8`, in its own worktree. Main and the settings/health branch are left unchanged.

- Forty-three Python tests pass, including a new fixed-route/CSP menu-asset check plus the previous backup/power/settings/security checks. Twenty-eight JavaScript status checks pass, covering exact archive identity, fresh observations, changed sources, copy failures, active copying, invalid percentages and refusing green at 100% pending progress. Sixteen Swift bridge checks pass for the fixed actions and rejecting other origins/ports/paths, subframes and arbitrary payloads; the fifteen existing Swift notification checks pass.
- Native app compiles for arm64 macOS 13. Menu JavaScript syntax passes. Isolated synthetic preview shows three cards, expandable observed progress, horizontal paging and keyboard navigation to the last of eleven repos; selection/scroll position persist through five-second refreshes. Browser console contains no errors. Synthetic examples are explicitly separate from real personal backups.
- No cloud computer, iCloud login, independent download or restore audit is configured in this pass, as requested. Full Git-history restore verification remains separate.

Installed menu observations: the native popover opens with three cards and correct real repo details; horizontal paging preserves selection across refreshes. Notification controls were toggled Off and restored On, the inline settings dialog saved unchanged defaults, and Repository Backups opened the correct iCloud folder in Finder. Startup retry targets the menu page, and the native popover receives keyboard focus. The earlier settings app/runtime/configuration is retained at `~/Library/Application Support/RepoHub/releases/settings-9f442b8`. Quit was not exercised; cloud restore verification remains deferred.

## Per-repo schedules and icon clarity — follow-up commit

- Fifty-one Python tests pass. New coverage checks independent repo frequencies/edit delays/pauses, combining timed and after-edit plans, per-repo cadence persistence, power changes preserving unattempted timers, override save/reload/default inheritance, stale override and default revisions, unknown/path-like IDs, arbitrary fields, invalid types, and Origin protection. Previous archive/content/retention/persistence/security checks still pass.
- The synthetic menu saved a 15-minute adapter override for one repo, retained it after reload, and returned it to Default using the inheritance checkbox. The icon disclosure lists every status; three cards remain visible and the corrected gear/action/status icons render as SVG. Native controls are disabled in the browser preview as expected. Cloud restore environment work remains deferred.

Installed follow-up observations: the native per-repo dialog opened for Excel development, unlocked custom fields, and saved Use defaults successfully. The main gear showed Default backup settings only. The installed full dashboard and menu preview both expanded the complete SVG icon legend; returning a synthetic custom schedule to inheritance displayed the actual defaults. Native UI interaction was stopped when an unsaved settings form appeared, leaving it intact. The disclosure uses a standard button rather than WebKit's summary control for reliable activation. Native compilation, 16 bridge checks, 15 notification checks, JavaScript syntax and 28 status-policy checks pass. The previous installed menu build remains at `releases/menu-9a6c26e`. No cloud login/download audit, physical power-source changes or deliberate sustained failures were performed.

## Battery manual-only follow-up

Battery defaults disable after-edits. Both default-settings views and menu-bar per-repo settings offer Automatic backups on battery; Off is manual-only, with frequency/after-edit controls disabled. Adapter has no extra toggle. Policy tests cover default quiet periods staying inactive, manual-only remaining paused even when cadence is due, and adapter scheduling remaining active. Existing policies, per-repo override behavior and manual backup checks remain covered.

Fifty-two Python tests pass; JavaScript syntax passes. Synthetic UI saved manual-only battery operation and retained its unchecked toggle and disabled controls after reload. Adapter remained unchanged and no adapter-only toggle appeared. Native compilation is unchanged in this settings commit.

## Finder shortcut and Things to know follow-up

The folder icon is a separate accessible button on every card and requests only a workspace ID. Native resolution fetches fresh helper status and checks current identity, name/path agreement, a direct child of the configured source root, an existing directory and no symlink escape. Thirty-five bridge checks pass, including valid repo opening targets and rejection of path-like/missing/oversized IDs, arbitrary payload fields, other frames/origins, outside paths, relative paths, missing dirs and symlinks. Native app compiles for arm64 macOS 13; 28 status policy checks and JS syntax pass. Synthetic menu preserves the three-card layout with independent Finder controls and expands Things to know.

Installed panel exposes separate Open [repo] in Finder buttons and the second disclosure, with three cards still visible. Actual native Finder activation could not be completed through UI automation because interaction was interrupted by user/window changes; path validation is covered by 35 executable Swift checks. The app job is running without reported app-log errors. Fifty-two Python tests pass; native compilation passes. Existing user custom schedules and saved defaults are preserved.
