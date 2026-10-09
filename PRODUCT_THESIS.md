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

The tested application release at `f9996ab` was promoted to main and deployed to both Macs on 2026-10-09. It includes the checked foundation items, continuous diagnostics, constrained agent exports and local bug/feature previews. Existing configuration was preserved; installer migration was not run. Earlier hashes below identify implementation milestones, not the current installed state. Green status currently requires a matching archive plus fresh macOS iCloud upload confirmation. The Air staging pilot now includes independent cross-device iCloud reception and restore verification; broader failure and UI coverage remains incomplete.

## Tier 0 — Publish the direction

- [x] Add this thesis to the existing latest work branch as a documentation commit.
- [x] Publish RepoHub as a public GitHub repository, keeping stable main and the current work branch available.

Published on 2026-10-09 at [yogoldy/RepoHub](https://github.com/yogoldy/RepoHub). GitHub visibility is Public and Issues are enabled. The default branch is main, now including this thesis and the latest tested application release. The existing `codex/backup-change-detection` branch is retained for its history. No diagnostics or backup archives were uploaded.

Publish app source and product documentation. Local diagnostics, personal backup archives, saved workspace JSON and credentials belong outside Git. Public source publication is separate from choosing a license or shipping a general-purpose installer.

## Tier 1 — Continuous diagnostics

**Goal:** When a repo appears to change unexpectedly or a backup stalls, the app can explain what happened over time.

The helper records diagnostics continuously from login, while the Mac is awake and the helper is running. Closing the menu-bar panel does not stop logging. Sleep and shutdown are gaps, not periods the app can observe; record startup, wake/resume and interruptions explicitly. “24/7” means an always-running local helper where macOS permits it, not activity while the computer is off.

- [x] **1A — Bounded log storage.** Add a structured JSONL writer under the app's local Application Support diagnostics directory, outside monitored repos and the saved workspace-data folder. Start with seven days or 100 MiB total retention, whichever limit is reached first; rotate individual files at 10 MiB. Restrict local file permissions. Handle full disks or logging errors without stopping backups. Test rotation, recovery and retention using synthetic data.
- [x] **1B — Change-detection evidence.** Log scan IDs, UTC timestamps, durations, scan/hash freshness, source-signature transitions, timestamp-only matches and counts of Finder/Git/repo-file differences. Record why a repo needs backup instead of treating its latest timestamp as proof of an edit. Verify that Finder browsing, timestamp changes and real file changes produce distinguishable events.
- [x] **1C — Backup and cloud evidence.** Log schedule decisions and power-source pauses, archive creation and verification stages, retries, failures, upload observations, stale checks, pruning decisions and recovery. Tie related events to a backup/run ID and the exact archive identity. Record state transitions and a periodic heartbeat; avoid dumping every unchanged five-second poll. Test error/recovery flows without damaging personal backups.
- [x] **1D — Agent-focused diagnostic export.** Provide a bounded structured event bundle and interpretation schema for agents, with consistent report-local aliases and a separate private alias key. Unknown text and nested payloads are excluded from the shareable copy. Test identifying paths, URL credentials, unusual filenames, bounds and permissions; local originals stay local. A human-readable debugging narrative is not required per Leo’s clarified goal. Export is currently a local command; report preview and Send belong to Tier 2.

Use an explicit event schema: schema/app version, UTC time, event, severity, run ID, repo alias, stage, duration, result and a small allowlist of diagnostic fields. Do not log file contents, environment dumps, Git remote URLs, authentication headers, API keys or tokens. File/path details needed for local diagnosis must be removed or aliased during export. Diagnostic storage must not itself trigger repo backups.

## Tier 2 — Report a bug or request a feature

**Goal:** A user describes a problem or desired change in prose and clicks Send; the owner receives a separately categorized GitHub issue suitable for human or AI review.

Settings contains two clear actions: **Report a bug** and **Request a feature**. Both open a small dialog with an editable title and prose field. A bug asks what happened and what the user expected; a feature asks what the user wants and why. Bug reports offer the sanitized diagnostic bundle. Feature requests omit logs by default, with an optional explicit attachment.

- [x] **2A — Bug-report dialog and local preview.** Build the prose form, recent diagnostics selection and exact report preview. Clearly disclose that the destination is a public GitHub issue. Let the user inspect/remove diagnostics and edit the report before Send. Test cancel, empty inputs, redaction and preserving a draft after failure.
- [x] **2B — Feature-request dialog and local preview.** Add the separate prose flow and preview, without requiring diagnostics. Keep feature requests distinct from bug reports in the local report record and UI.
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

1. Pick one unchecked atomic item, next **2C: choose and implement GitHub authentication and submission**; the local bug/feature previews are complete, while delivery receipts and broader Tier 5C coverage remain open.
2. Implement it on the authorized work branch, with proportionate checks against synthetic data and a live UI check when behavior changes.
3. Commit the implementation separately from the next item. Add its SHA and evidence to this checklist; a plan or screenshot alone does not mark a backend feature complete.
4. Preserve stable main until the completed tier is reviewed for merging. Do not enable cloud/AI accounts, telemetry or scheduled maintainer agents as a side effect.

The product should stay visually small: repo cards and useful status first; a gear for defaults/setup/reporting; per-repo timing in the menu bar. Diagnostics and integrations should improve confidence without turning the normal view into a developer console.

## Implementation evidence

**Tier 1A — `6826b7e` (2026-10-09):** structured local logs, owner-only permissions, 10 MiB rotation, seven-day/100 MiB retention, startup events, throttled heartbeats and observed runtime gaps. Sixty-five Python checks pass, including nine storage/failure/privacy/concurrency regressions. Native macOS 13 compilation passes after adding the Python module to installer packaging. Scan/display evidence and local dogfooding follow in the separate Tier 1B commit; no diagnostic upload is enabled.


**Tier 1B — `ec5cabe` (2026-10-09):** scan IDs, durations, signature transitions, hash receipts, classified Finder/Git/repo-file differences and source/archive references are logged. Menu and full-app renderers report their actual displayed label, phase and readiness against a shared backend observation ID. Its identity includes publication errors and saved archive hashes, so changing readiness inputs cannot silently reuse a previous observation. A local report reader correlates same-observation receipts; absent receipts are not counted as agreement. Seventy-three Python tests, 34 JavaScript status checks and diagnostic delivery checks pass.

Installed dogfooding recorded seven Finder-only repo alerts with zero project-file differences, and 34 of 34 native-menu/full-app comparisons agreed. The readable case and detailed evidence remain in local Application Support, outside Git; this capture cannot explain behavior before logging began. Backup/status policy was not changed in this diagnostic pass. Tier 1C stage instrumentation, Tier 1D shareable export and the reporting dialogs remain separate unfinished items.


**Finder-trigger and repo-scope follow-up (2026-10-09):** the diagnostic case motivated a narrow `.DS_Store` trigger exception. Full hash differences remain disclosed with an information icon; they are not relabeled as full matches. Three repeated Finder-only writes create no archives and do not rewrite the iCloud index. Synthetic whole-schedule and targeted-backup checks prove that only the selected meaningfully changed repo gets a replacement; ignored files, Git history, AppleDouble data, corruption repair and existing upload-gated retention remain covered. Eighty-three Python tests, 45 JavaScript status checks, diagnostic delivery checks and native macOS 13 compilation pass. Native/browser installation observations are recorded in VERIFICATION.md. This follow-up is one implementation commit on the existing work branch; main stays separate.


**Tier 1C — Backup lifecycle and icon decisions (2026-10-09):** schedule decisions disclose the effective frequency/edit delay and power source, quiet-period and retry waits. Selected decisions share a run ID with archive creation, hash verification, transfer and publication stages. Reuse, repair, per-repo errors, run completion and restart interruptions are recorded. New archive indexes persist the creating run ID, so macOS upload observations, stale receipts, upload-gated retention and individual prune operations can refer to the exact archive and run across restarts. Unchanged scheduling/upload/retention observations are throttled to a per-minute heartbeat. Existing archives without a run ID retain their archive reference; prior unlogged events are not reconstructed.

Menu/app presentation receipts now link to those run/archive identities. Backend evidence includes freshness, change classification, copy state and verification/upload archive identities. A diagnostic-only comparison explains the rendered icon and flags disagreement with backend inputs separately from disagreement between views; neither a UI receipt nor an icon is upload proof. This does not change status or scheduling policy. The local summary includes the latest 200 lifecycle events and bounded input disagreements. Shareable export/reporting dialogs and independent cloud restores remain separate work.


**5C pilot preparation — Controlled receive-and-restore audit:** `restore_audit.py` and [the cloud handoff](docs/CLOUD_RESTORE_HANDOFF.md) prepare a private offline test. The receiving cloud agent does not need iCloud access. Expected file/Git facts are independently captured from the matching live source, not derived from the test archive. Verification checks supplied identities, safe extraction, every manifest entry, Git integrity/history and input immutability, with stage logs and explicit unsupported cases. This prepares the experiment; Tier 5C stays unchecked until actual private iCloud-downloaded inputs are independently restored. Direct authenticated cloud retrieval and application execution remain outside this pilot.

**5C Air staging pilot — Real two-Mac evidence:** See [the controlled Air experiment](docs/AIR_STAGING_TEST.md). A full-history public fixture passed 34 live staging assertions, real after-edit scheduling, upload observations, and an independent restore of the iCloud-received copy on the main Mac. The experiment exposed and corrected symlink-mode preservation in the restore checker. Tier 5C remains unchecked for its broader coverage, including unusual Git layouts and failure cases. Next diagnostic acceptance gap: actual rendered progress percentages, visibility and selected-repo detail must be correlated with backend observations; current receipts cover icons/labels only.

**Verification availability — Source and synthetic coverage:** `c035666` separates verification I/O failures from checksum/archive corruption, preserves the current archive when verification is unavailable, and records a bounded `verification_deferred` lifecycle event. [The policy](docs/VERIFICATION_AVAILABILITY.md) documents the conservative retry behavior and synthetic regression coverage. Concrete private repository experiments and diagnostic reports remain local and outside Git.

**Tier 1D — Agent export (2026-10-09):** [Export contract and usage](docs/DIAGNOSTIC_EXPORT.md) describe the machine-readable bundle, report-local alias relationships, separate private key and incomplete-evidence rules. Privacy/bounds regressions and the full 107-test Python suite pass on both Macs. A small controlled Air fixture exercises real backups, file changes, verification, upload acknowledgement and export correlation. Settings/reporting UI and external submission remain Tier 2; no diagnostics are published.

**Tiers 2A/2B — Local report previews (2026-10-09):** [Preview behavior and boundaries](docs/REPORT_PREVIEW.md) describe separate bug/feature forms, the proposed public payload, optional bounded diagnostic files, private local drafts and failed-request prose preservation. The full 113-test Python suite passes on both Macs, browser interactions exercise both flows, JavaScript checks pass and native compilation passes. Sending is disabled pending Tier 2C; the stable installed app and main remain unchanged.

**Diagnostic payload hardening (2026-10-09):** Export schema v2 replaces broad vocabulary matching with explicit per-field types and enums, rejects unknown events and arbitrary text, removes wall-clock dates/exact sizes, caps counts, rounds progress and creates fresh alias namespaces per report. Adversarial privacy tests and 118 total Python tests pass on both Macs. User prose stays separate, with a confidentiality reminder. Send remains disabled; concrete dogfooding logs and alias keys stay local.

**Release deployment — `f9996ab` (2026-10-09):** Promoted to GitHub main and deployed to both Macs. All 21 packaged Python/web files were checked against the release manifest, and each loaded helper’s build identity was checked against its installed source. Live checks verified the served report interface, authenticated report preview API, export schema v2, private-key exclusion and diagnostic recording. Configuration and scheduling files were preserved. Previous runtimes and local deployment receipts are retained for rollback. The first Air service re-registration attempt rolled back; restarting its existing registered launch job succeeded. Native source was unchanged. No forced backup/restore rerun or external report submission was performed. Next: Tier 2C GitHub authentication and submission, then Tier 2D delivery/retry handling.

## Cross-cutting quality — Golden rules

- [x] Document known failure modes, their diagnostic trails, required responses, narrow fixes and remaining exposure in [the quality register](docs/quality/FAILURE_MODES.md). Concrete private incident records remain local.
- [x] Add an executable domain release gate linking each rule to tests that must actually execute and pass; validate runtime/HTML packaging, JavaScript behavior/syntax and native builds/checks. Receipts identify source revision/fingerprint, dirty state and pending manual evidence.
- [x] Wire the synthetic macOS gate into GitHub push/PR checks and agent release instructions. Branch protection itself remains unchanged.

[Gate usage and limits](docs/quality/RELEASE_GATE.md) distinguish an automated pass from live deployment/provider/hardware acceptance. Application behavior and the installed release are unchanged by this quality-tooling work.
