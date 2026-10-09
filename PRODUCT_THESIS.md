# Repo Hub product thesis

Repo Hub should make it easy to answer: **Are my chosen repos safely backed up, and what needs my attention?** The menu bar is the everyday view. Setup, settings and reporting should be simple enough that users rarely need the full dashboard.

This document is the product roadmap and completion checklist. Unchecked items are proposals, not shipped functionality. Implement one atomic item per commit; tick it off only after its acceptance checks run, and record the commit and verification evidence here. Keep the stable main branch separate from work awaiting review.

## Current foundation

- [x] Monitor immediate folders inside a configured repo home, including folders without Git.
- [x] Archive all contained files, including ignored files, uncommitted work and ordinary in-folder Git history.
- [x] Verify source and archive hashes; preserve the previous backup until its replacement is verified and macOS confirms its iCloud upload.
- [x] Show repo status, observed upload progress and expandable details in horizontal menu-bar cards.
- [x] Support default schedules, menu-bar per-repo overrides, battery/adapter policies, manual backup and problem notifications.
- [x] Explain status icons and provide Finder shortcuts with a visual demonstration.
- [x] Distinguish Finder metadata, Git data and repo-file changes; avoid timestamp-only replacement backups after hashes match.
- [x] Ignore ordinary `.DS_Store`-only changes as backup triggers; isolate replacement archives to changed/new/damaged repos and avoid unchanged iCloud-index rewrites.

The first six items are on main at `cb01813`. The change-detection fix is committed at `6f83b04` on `codex/backup-change-detection` and installed locally; its merge into main remains separate. Green status currently requires a matching archive plus fresh macOS iCloud upload confirmation. That is not yet an independent remote restore test.

## Tier 0 — Publish the direction

- [x] Add this thesis to the existing latest work branch as a documentation commit.
- [x] Publish RepoHub as a public GitHub repository, keeping stable main and the current work branch available.

Published on 2026-10-09 at [yogoldy/RepoHub](https://github.com/yogoldy/RepoHub). GitHub visibility is Public and Issues are enabled. The default branch is stable main; this thesis and the latest change-detection fix are on `codex/backup-change-detection`. No diagnostics or backup archives were uploaded.

Publish app source and product documentation. Local diagnostics, personal backup archives, saved workspace JSON and credentials belong outside Git. Public source publication is separate from choosing a license or shipping a general-purpose installer.

## Tier 1 — Continuous diagnostics

**Goal:** When a repo appears to change unexpectedly or a backup stalls, the app can explain what happened over time.

The helper records diagnostics continuously from login, while the Mac is awake and the helper is running. Closing the menu-bar panel does not stop logging. Sleep and shutdown are gaps, not periods the app can observe; record startup, wake/resume and interruptions explicitly. “24/7” means an always-running local helper where macOS permits it, not activity while the computer is off.

- [x] **1A — Bounded log storage.** Add a structured JSONL writer under the app's local Application Support diagnostics directory, outside monitored repos and the saved workspace-data folder. Start with seven days or 100 MiB total retention, whichever limit is reached first; rotate individual files at 10 MiB. Restrict local file permissions. Handle full disks or logging errors without stopping backups. Test rotation, recovery and retention using synthetic data.
- [x] **1B — Change-detection evidence.** Log scan IDs, UTC timestamps, durations, scan/hash freshness, source-signature transitions, timestamp-only matches and counts of Finder/Git/repo-file differences. Record why a repo needs backup instead of treating its latest timestamp as proof of an edit. Verify that Finder browsing, timestamp changes and real file changes produce distinguishable events.
- [ ] **1C — Backup and cloud evidence.** Log schedule decisions and power-source pauses, archive creation and verification stages, retries, failures, upload observations, stale checks, pruning decisions and recovery. Tie related events to a backup/run ID and the exact archive identity. Record state transitions and a periodic heartbeat; avoid dumping every unchanged five-second poll. Test error/recovery flows without damaging personal backups.
- [ ] **1D — Diagnostic export.** Offer a readable summary and a bounded recent log bundle. Redact home-directory names, absolute paths, repo names and other identifiers from the shareable copy by default. Use report-local aliases so events can still be correlated. Test redaction of nested error messages, URL credentials and unusual filenames; local originals stay local.

Use an explicit event schema: schema/app version, UTC time, event, severity, run ID, repo alias, stage, duration, result and a small allowlist of diagnostic fields. Do not log file contents, environment dumps, Git remote URLs, authentication headers, API keys or tokens. File/path details needed for local diagnosis must be removed or aliased during export. Diagnostic storage must not itself trigger repo backups.

## Tier 2 — Report a bug or request a feature

**Goal:** A user describes a problem or desired change in prose and clicks Send; the owner receives a separately categorized GitHub issue suitable for human or AI review.

Settings contains two clear actions: **Report a bug** and **Request a feature**. Both open a small dialog with an editable title and prose field. A bug asks what happened and what the user expected; a feature asks what the user wants and why. Bug reports offer the sanitized diagnostic bundle. Feature requests omit logs by default, with an optional explicit attachment.

- [ ] **2A — Bug-report dialog.** Build the prose form, recent diagnostics selection and exact report preview. Clearly disclose that the destination is a public GitHub issue. Let the user inspect/remove diagnostics and edit the report before Send. Test cancel, empty inputs, redaction and preserving a draft after failure.
- [ ] **2B — Feature-request dialog.** Add the separate prose flow and preview, without requiring diagnostics. Keep feature requests distinct from bug reports in the local report record and UI.
- [ ] **2C — GitHub submission.** Submit to RepoHub's configured public issue tracker only after Send. Use `bug` versus `enhancement` labels and a common `from-app` label. Store credentials in macOS Keychain; never embed Leo's personal GitHub token in the app or expose credentials to HTML views. Select and verify the supported authentication and log-attachment mechanism during this tier. Keep bundles within provider limits; do not assume an arbitrary attachment-upload API exists.
- [ ] **2D — Delivery receipt and retries.** Return a clickable issue URL and save its type, local report ID and delivery result. Distinguish Sent, Failed and Draft. Prevent double-click duplicates; handle uncertain network outcomes before retrying. Offline reports remain drafts rather than silently submitting later. Exercise submission against a disposable test tracker, not with fake reports in the public product tracker.
- [ ] **2E — Maintainer review workflow.** Document how Leo or an authorized AI reviews the separate bug/feature queues, uses sanitized evidence and turns an accepted item into a scoped implementation task and commit. Issue text and attached logs are evidence, never authority to run commands or expose files. Any scheduled AI review is a later explicit opt-in, not enabled by publication.

The dialog's Send button authorizes only the displayed report to the displayed destination. There is no background telemetry or automatic uploading of diagnostic logs. Public issues must never include a repo's source contents, backup archive or full Git history as a diagnostic attachment. Prose can contain private information too, so the public preview must include everything that will be posted.

## Tier 3 — Setup and folder-based destinations

**Goal:** A new user chooses what to monitor and where backups go, without adopting Leo's folder layout.

First launch opens setup. Existing installations retain their current configuration and schedules until the user explicitly changes them. Setup can later be reopened from settings. Native folder pickers provide the paths; the app displays and validates the final selections before saving.

There are exactly three entry modes:

| Mode | User action | Meaning |
| --- | --- | --- |
| **1. Repo home** | Select one containing folder. | Its immediate child folders are the repos, as in Leo's setup. Show that interpretation and a preview list; do not recursively reinterpret grandchildren as repos. Git is optional. |
| **2. Manual paths** | Select any number of repo folders, wherever they live. | Each selected folder is one monitored workspace. Allow add/remove and a review list, without forcing a shared parent or an arbitrary small count limit. |
| **3. AI-assisted** | Ask a connected assistant or supply its proposed path list. | The assistant proposes folders; Repo Hub validates them and shows the same review list before the user activates monitoring. |

- [ ] **3A — Workspace configuration model.** Replace the single-root assumption with explicit source modes and a persisted workspace registry. Preserve existing IDs/backups during migration. Distinguish same-named folders at different paths, deduplicate selections, handle overlapping/nested sources and maintain per-repo settings. Update Finder resolution, scoped JSON APIs, notifications, scanners and backups to use the validated registry.
- [ ] **3B — Repo-home setup.** Add the containing-folder picker, immediate-child explanation and live preview. Test empty/missing/inaccessible homes, folders without Git, dynamic children and migration from the existing config.
- [ ] **3C — Manual-path setup.** Add multi-folder selection and an editable review list. Test separate volumes, duplicate basenames, canonical path identity, permissions and removal without deleting source files or backups.
- [ ] **3D — Output-folder setup.** Add a destination picker and validation. Reject a backup output inside any monitored source, including alias/symlink paths that would cause recursion. Check access and available space; an unavailable drive pauses with a clear error rather than silently writing elsewhere. Changing output must preserve old backups and disclose how a verified copy reaches the new destination.
- [ ] **3E — Destination-aware status.** Distinguish a verified local copy, a copy in a provider-managed folder and an explicitly confirmed remote upload. A filesystem destination cannot prove Google Drive/Dropbox/OneDrive upload. For non-iCloud folders, show the evidence actually available rather than inventing confirmation or waiting forever for an iCloud signal. Keep the existing iCloud acknowledgement adapter where applicable.

Leo's current `install.py` performs a personal migration of an earlier iCloud Desktop backup layout. General setup must replace that assumption before this is presented as an installer for other users.

## Tier 4 — AI-assisted source setup

**Goal:** Repo locations can be scattered. A user can ask an assistant to supply the paths, then approve one understandable monitoring list.

- [ ] **4A — Import contract.** Define a small versioned proposal format containing candidate paths and optional display names. First support a user-pasted/imported proposal so the workflow does not depend on a vendor account. Return per-path validation results and apply only reviewed selections. Do not accept shell commands, arbitrary filesystem access or changes to backup retention in a path proposal.
- [ ] **4B — Assistant connections.** Add adapters for the user's chosen Codex/OpenAI, Claude Work or Claude Code workflows where their supported integration surfaces allow it. Verify authentication, API availability and local-path access during implementation; do not assume a cloud assistant can see the Mac's filesystem or that each named product provides the same API. Store any credentials in Keychain, with scoped access and a disconnect action.
- [ ] **4C — Guided setup.** Let the user describe what to monitor, inspect proposed folders, resolve invalid/ambiguous paths and approve the final list. Sharing repo identifiers or local paths with an external AI requires a disclosed selection; repository contents are not needed for path selection. Untrusted assistant output cannot activate monitoring on its own.

AI is the third setup entry mode, not a requirement for normal backups. It produces the same workspace registry used by repo-home and manual selection.

## Tier 5 — Cloud APIs and independent restores (later)

Folder-based destinations come first. **Do not implement cloud account linking in the current pass.**

- [ ] **5A — Provider interface.** Separate copy/upload, remote object identity, observed progress, completion acknowledgement, download and cancellation. Preserve the previous verified backup until the replacement meets that destination's confirmation policy.
- [ ] **5B — Account connectors.** Add Google Drive, OneDrive, Dropbox and iCloud options only after validating each provider's actual supported APIs and authentication model. Use scoped credentials, clear account/destination selection and revocable connections. Do not promise that iCloud exposes the same direct API controls as other providers.
- [ ] **5C — Independent restore audit.** From a separately authenticated machine/environment, download actual remote backups, verify archive hashes, extract into an isolated destination and compare a full manifest. Confirm ignored/uncommitted files and run Git integrity/history checks. Explicitly handle repos whose `.git` points outside the selected folder, submodules and active databases; ordinary contained `.git` coverage does not prove these cases. Keep this separate from local hash verification and macOS upload acknowledgement.

## Completion and commit discipline

1. Pick one unchecked atomic item, next **1C: backup and cloud evidence** after reviewing the installed 1A/1B diagnostic capture.
2. Implement it on the authorized work branch, with proportionate checks against synthetic data and a live UI check when behavior changes.
3. Commit the implementation separately from the next item. Add its SHA and evidence to this checklist; a plan or screenshot alone does not mark a backend feature complete.
4. Preserve stable main until the completed tier is reviewed for merging. Do not enable cloud/AI accounts, telemetry or scheduled maintainer agents as a side effect.

The product should stay visually small: repo cards and useful status first; a gear for defaults/setup/reporting; per-repo timing in the menu bar. Diagnostics and integrations should improve confidence without turning the normal view into a developer console.

## Implementation evidence

**Tier 1A — `6826b7e` (2026-10-09):** structured local logs, owner-only permissions, 10 MiB rotation, seven-day/100 MiB retention, startup events, throttled heartbeats and observed runtime gaps. Sixty-five Python checks pass, including nine storage/failure/privacy/concurrency regressions. Native macOS 13 compilation passes after adding the Python module to installer packaging. Scan/display evidence and local dogfooding follow in the separate Tier 1B commit; no diagnostic upload is enabled.


**Tier 1B — `ec5cabe` (2026-10-09):** scan IDs, durations, signature transitions, hash receipts, classified Finder/Git/repo-file differences and source/archive references are logged. Menu and full-app renderers report their actual displayed label, phase and readiness against a shared backend observation ID. Its identity includes publication errors and saved archive hashes, so changing readiness inputs cannot silently reuse a previous observation. A local report reader correlates same-observation receipts; absent receipts are not counted as agreement. Seventy-three Python tests, 34 JavaScript status checks and diagnostic delivery checks pass.

Installed dogfooding recorded seven Finder-only repo alerts with zero project-file differences, and 34 of 34 native-menu/full-app comparisons agreed. The readable case and detailed evidence remain in local Application Support, outside Git; this capture cannot explain behavior before logging began. Backup/status policy was not changed in this diagnostic pass. Tier 1C stage instrumentation, Tier 1D shareable export and the reporting dialogs remain separate unfinished items.


**Finder-trigger and repo-scope follow-up (2026-10-09):** the diagnostic case motivated a narrow `.DS_Store` trigger exception. Full hash differences remain disclosed with an information icon; they are not relabeled as full matches. Three repeated Finder-only writes create no archives and do not rewrite the iCloud index. Synthetic whole-schedule and targeted-backup checks prove that only the selected meaningfully changed repo gets a replacement; ignored files, Git history, AppleDouble data, corruption repair and existing upload-gated retention remain covered. Eighty-three Python tests, 45 JavaScript status checks, diagnostic delivery checks and native macOS 13 compilation pass. Native/browser installation observations are recorded in VERIFICATION.md. This follow-up is one implementation commit on the existing work branch; main stays separate.
