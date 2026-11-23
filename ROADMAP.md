# RepoHub roadmap

This is where RepoHub is headed. It lists what exists, what is next and what is deliberately not planned. For how the app works today, see [How RepoHub works](docs/HOW_IT_WORKS.md); to help, see [CONTRIBUTING](CONTRIBUTING.md). A roadmap entry is a direction, not a promise or a schedule.

## Principles

- **Honest status.** The app tells the truth about whether a backup is safe: verified contents plus macOS-confirmed upload of the current archive, and "Unknown" when it can't tell.
- **Safe by default.** Backups are never deleted before a verified, uploaded replacement exists (the one timed exception: items from removed linked folders are kept for 30 days), and the app never changes the user's folders.
- **Usable by anyone.** Clear setup, plain-language status, recovery steps an ordinary user can follow, and sensible defaults. This means open source and understandable, not monetized.
- **Small and local.** RepoHub runs on the user's Mac. New infrastructure is added only when a feature truly needs it.
- **Evidence over claims.** Changes ship with tests that reproduce the failure they fix. Documents separate what is tested from what is assumed.

## Delivered

- Verified backups: complete archives (including `.git`, uncommitted and ignored files), full content hashing of source and archive, and latest-only retention gated on macOS's upload confirmation.
- A menu-bar app with repo cards, per-repo and default schedules (battery and power adapter), after-edit backups, notifications and a full dashboard.
- First-run setup: choose one parent folder, individual folders, or discover Git repos; choose an iCloud Drive destination with an access check; review before anything is saved. Readable backup folder names that follow your repo names.
- Included linked folders and linked checkouts, saved as separate verified archives, with a 30-day keep window under latest-only retention once a backup observes removal or exclusion. An unreachable source keeps its last archive without starting that timer.
- Diagnostics that stay on the Mac, with a typed, sanitized export and an explicit, previewed bug report to the public GitHub tracker.
- Signed, notarized releases delivered through Sparkle with Stable and Dev channels, an automatic helper restart, and a one-time login-item registration attempt after setup, with the resulting macOS state shown in Settings.
- A restore audit that independently verifies an archive against a baseline captured from the live source.

## Next

1. **Prove a fresh install on a clean Mac.** Install a release on a Mac that has never run RepoHub, run setup, make a backup, restart and restore, and fix what it exposes. This includes checking that the login item registers and that the helper restarts after a crash.
2. **Reports without a GitHub account.** Let any user send a bug report or feature request, with optional sanitized diagnostics, without a GitHub account or token. A small hosted service would post accepted reports through a narrowly scoped GitHub App, keeping credentials on the service and never in the Mac app. Payload limits, abuse controls, duplicate and retry handling and delivery receipts come first. The user would still preview the exact text and explicitly press Send.
3. **Other sync folders.** Support any Finder-accessible sync folder (Google Drive, OneDrive and others), not only iCloud Drive. This must distinguish a verified local copy from a confirmed remote upload, and say so when remote confirmation isn't available instead of inventing success.
4. **A buildable fork.** Document and parameterize the app identifier, update feed, signing identity, and the two host labels that Stable promotion currently requires, so others can build and sign their own copy.
5. **Harden for shared Macs.** Authenticate callers to the local helper per user (for example with a private socket or a token file only the user can read) instead of handing the write token to any local request. Until then, the app is meant for a Mac you don't share.
6. **Reliability and tidy-up.** Update checks that never freeze the panel, a bounded quit during a long backup, less repeated re-hashing of a repo being edited, bounded notification history, simpler release evidence, and a real version-number scheme.
7. **TestFlight evaluation (low priority).** Consider it as an extra distribution route, with tester feedback and crash reports. It would not replace the Sparkle channels.

## Not planned

- CloudKit or remote push notifications.
- Direct connections to cloud-provider accounts (sync folders are used instead).
- Monetization, accounts or telemetry.
