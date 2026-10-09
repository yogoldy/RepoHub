# Verification — 2026-10-09

- Eight synthetic unittest checks passed: complete archives including hidden/ignored files and symlinks; source-change rejection; unchanged skip and retained versions; Finder-metadata display filtering without backup exclusion; distinct staged/unstaged/untracked counts; missing archive detection and recreation; scoped view/data paths; HTTP origin/Host checks, JSON revisions/conflicts, view injection and app-data snapshot.
- Native Swift app compiled for arm64-apple-macos13.0; Mach-O minimum OS and Info.plist both declare 13.0. The installed app launches successfully on this Mac. This corrects the earlier inferred macOS 28 minimum.
- Installed native dashboard showed 11/11 matching snapshots. Advanced was visibly off, then on with separate worktree counts, then off again.
- Synthetic HTML notes view saved JSON through the scoped bridge and retained it after reloading the page.
- Initial full run published checksum-verified snapshots for all eleven repo folders plus saved app data. Previous repo mirror retained with matching file/byte/symlink inventory; older versions remained in place.
- Helper and frontend login LaunchAgents were loaded and running. The former cloud-Desktop backup job was unloaded and its script retargeted to Repository Backups. Cloud Desktop contents moved to Trash after preserving the repo mirror; a subsequent empty cloud Desktop folder was removed but returned again empty. Its recreation source remains unconfirmed; no repo mirror is being written there by the retired job.

## Deliberate skips and limits

No real logout/reboot was performed. The menu-bar dropdown was not inspected through the UI; its app compiled and is running. iCloud server-side upload completion was not verified. Metadata comparison is not a repeated byte-by-byte source audit; see README for detection and live-copy consistency limits. Existing source repos were not edited, cleaned or committed. No backup retention deletion was introduced.
