# Verification — 2026-10-09

## Current checks

- Nineteen synthetic tests pass. Content checks detect equal-size edits with restored modification timestamps, reject content changes during copying, compare actual archived members including hardlinks/empty directories, and detect/repair corrupted archives. Retention tests cover copy/index failures, stale observations, and waiting for upload confirmation. Existing JSON, path, Host/Origin, Git and backup-content tests pass.
- Both native Swift executables compiled for arm64-apple-macos13.0. JavaScript syntax check passed. The installed app displays separate content verification and per-archive upload status; green requires both checks.
- The live full content audit verified all eleven repo copies. macOS reported three uploaded repo archives and eight repo upload errors, plus a saved-data upload error. Every affected upload reports NSCocoaErrorDomain 4355 (iCloud server connection unavailable). Read-only quota check reported 1,600,548,539,775 bytes remaining. Apple's live status page listed iCloud Drive and account sign-in as available at 1:29 PM Eastern. Those observations rule out exhausted storage and a reported general outage; they do not identify the exact connection/session cause.
- A real RepoHub archive was restored into a temporary folder with native tar. All 138 entries matched file bytes, modes and structure, and restored Git passed `git fsck --full`. The temporary restored copy was removed.
- The upload helper successfully reads Apple's documented per-file status keys outside the tool sandbox. Missing flags, failed helpers and conflicts cannot become Uploaded. The helper reports error codes without dumping account identifiers or error userInfo.

## Behavior and deliberate limits

Deep content checks run every 15 minutes, at startup/backup time, and on Refresh; normal metadata and upload checks run every 30 seconds. The displayed verification time identifies the last observation. New archives are decompressed and compared to before/after source content hashes, and destination archive bytes are checksum verified. Existing verified archive content digests can be reused only alongside a fresh source-content hash and a fresh archive checksum.

The prior archive is kept until the replacement is verified, indexed and explicitly confirmed uploaded. Legacy backups and saved JSON are preserved. The iCloud connection issue remains unresolved: no Apple Account, network, sync settings or daemon resets were performed. No logout/reboot or menu-bar dropdown UI inspection was done. Upload confirmation is macOS acknowledgement, not an independently redownloaded server copy. Live copies are not atomic database/filesystem snapshots. Source repos other than RepoHub were not edited or committed.
