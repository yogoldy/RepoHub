# RepoHub product roadmap

RepoHub should make it easy to answer: **Are my chosen repos safely backed up,
and what needs my attention?** The menu bar is the everyday view.

## Scope and status — updated October 20, 2026

This is the current reference for Leo's unfinished product requests. It supersedes
the previous tiered roadmap at source
`38d354d5ade1cc5664c43a15cb680bc31b0d0019`; Git retains that version and its
implementation history. Leo approved the revised scope below on October 17.

- **Requested:** agreed product direction, with implementation still pending.
- **Implemented:** code exists; this does not imply every installed-Mac condition
  has been verified.
- **Awaiting verification:** the remaining work is evidence or acceptance rather
  than a new feature.
- **Superseded:** removed from the active roadmap by Leo's revised direction.

Roadmap entries do not by themselves start feature implementation, set an
implementation order, authorize external submissions, or authorize a Git push.
Complete approved work in scoped commits with proportionate tests and evidence.

## Current local update batch

Leo authorized the package-resource change below as the first implementation in
this batch. The remaining requested features still need their own implementation
scope; this batch stays local until promotion is authorized.

- [x] **Explicit packaged web assets:** the bundle builder copies a declared list
  rather than the whole `web` directory. Extra local files are excluded; missing
  or linked required files fail packaging. The existing 17 served assets remain.
  GR20 requires resource-selection and omitted-route counterexamples; the macOS
  gate also builds the complete app. See [the packaging boundary](docs/quality/FAILURE_MODES.md#gr20--coordinated-app-replacement).
- [x] **Calmer stale-status display and Rescan now:** missing fresh evidence uses
  neutral waiting copy on the cards and detail pane, while raw freshness and
  non-green readiness remain unchanged. A visible scan action uses the existing
  guarded scan API without creating a backup. Diagnostic policy 7 retains older
  wording for historical receipts; GR06 covers the waiting/recovery and request
  boundaries. Installed-Mac delivery remains part of the next update.
- [x] **Prominent scan and backup controls:** Back up now and Rescan now share
  equal-width gold buttons with distinct circular-arrow/scan icons. Repository
  Backups is a full-width navigation row with a folder icon, white label, trailing
  chevron and subtle hover fill, followed by notifications. The footer keeps only
  the last-check time and Quit. Scan requests preserve the icon through pending
  and failed requests. This is a local presentation change, not a new backup rule.
- [x] **First-run setup candidate:** the approved five-step welcome window,
  one iCloud destination, readable folder layouts, reviewed Git discovery and
  recoverable configuration saves are integrated. The first protected release
  passed the clean gate and installed migration; a draft-reload correction has
  its own final delivery checks. See [the implementation record](docs/FIRST_RUN_SETUP.md).

## Existing foundation

The following are implemented and must not be rediscovered as unfinished features:

| Capability | Evidence and remaining boundary |
| --- | --- |
| Repo-home and individually chosen folders, stable workspace identities, native pickers and explicit review/save | [Workspace configuration](docs/WORKSPACE_CONFIGURATION.md). Environmental acceptance remains separate. |
| Complete archives, source/archive hash verification, schedules and conservative replacement of previous backups | [Verification](VERIFICATION.md) and [Golden Gate](docs/quality/RELEASE_GATE.md). Existing backup-preservation requirements continue. |
| Continuous local diagnostics, constrained export, separate bug/feature forms, reviewed GitHub submission and durable delivery receipts | [Reporting contract](docs/REPORT_DELIVERY.md). Easier non-owner setup and maintainer review remain requested below. |
| Coordinated app/helper/interface packaging, Sparkle, secure update-key custody, HTTPS feed and automatic publication after protected main checks | [Personal release delivery](docs/RELEASE_DELIVERY.md). Apple signing and permission continuity remain separate. |
| Settings/About pages, explicit Save changes, selection-only repo details and menu-bar number preferences using existing card statuses | [Info view](docs/INFO_VIEW.md), [status policy](docs/STATUS_CLARITY.md) and the [menu-bar appearance reference](README.md#menu-bar-repo-cards). New UI work must retain shared state rules and diagnostic disagreement checks. |

## Requested features

### R1 — Choose the backup destination

**Status: Implemented candidate; awaiting acceptance.** This release selects one
folder inside iCloud Drive; other providers and multiple destinations remain
outside it. See [first-run setup](docs/FIRST_RUN_SETUP.md).

- Let the user select and review a destination through a native folder picker.
- Validate access, available space and source/destination separation, including
  aliases and symlinks. Prevent recursive backups.
- An unavailable or disconnected destination must pause with a clear explanation.
  Do not silently redirect a backup elsewhere.
- Changing destinations must preserve existing archives and disclose how a
  verified replacement reaches the new location. Saving a path is not proof of a
  successful copy.

### R2 — Validate Finder-accessible sync folders

**Status: Requested.** Retains destination-aware status (3E), with the revised
folder-based provider scope.

- Support selecting ordinary Finder paths, including iCloud Drive, Google Drive,
  OneDrive and other locally accessible sync folders. No direct provider-account
  connection is planned.
- Validate actual backup creation, archive hashes, isolated extraction/restore and
  failure/recovery at the selected path. Exercise unavailable drives, denied
  access and provider-managed files where applicable.
- Clearly distinguish a verified local destination copy from confirmed remote
  upload. A provider's name or folder location alone cannot establish upload.
  Preserve the existing iCloud evidence adapter where applicable; when remote
  confirmation is unavailable, say so rather than inventing success or waiting
  forever for an iCloud-only signal.
- Preserve previous good backups when confirmation is missing. Any non-iCloud
  replacement/retention policy must be explicit and tested before cleanup.

These are destination tests, not a new cloud API, remote-verification service or
separate expanded independent-restore product. Existing restore tools and pilot
records remain evidence with their original limits.

### R3 — Replayable visual onboarding

**Status: Implemented candidate; awaiting acceptance.** The five-step welcome
window supports fresh setup and an existing user's prefilled review without
changing configuration before explicit apply. See [first-run setup](docs/FIRST_RUN_SETUP.md).

Explain sources, destination, schedules, manual backup, verification and upload
status through a short visual walkthrough tied to actual controls. Offer Skip,
Back, Next and replay from Settings, keyboard support and reduced motion.
Demonstrations must be recognizable as demonstrations and must not change settings
or start backups. Preserve existing users' configuration and avoid forcing the
tutorial on every launch.

### R4 — Preserve repo names in backup folders

**Status: Implemented candidate; awaiting acceptance.** Revised by Leo on October 18: one naming behavior,
without custom labels.

- Name each workspace's backup folder after its source folder, preserving the
  repo name. Do not append an arbitrary identifier, hash, numeric suffix or
  “Backup” label. No custom naming setting is requested.
- Keep stable workspace IDs, source bindings and verification hashes in internal
  registry/index metadata, separate from the visible folder name. The original
  layout used a slug plus a shortened identity hash as both workspace ID and
  destination directory; migration retains that ID and its verification history.
- Validate names using the destination filesystem's rules. If two repos would
  have the same destination name, including case/normalization collisions, show
  the conflicting source paths and require an explicit destination/layout
  resolution before proceeding. Never silently rename, merge or overwrite them;
  reviewed parent grouping uses the shortest distinguishing source ancestry.
- Migrate existing suffixed folders without losing archives, indexes or schedules.
  Recheck upload evidence at each changed path. Preserve recovery and show the
  resulting path. Existing backups change only when reviewed setup is applied.

### R5 — Recursive Git-based repo discovery

**Status: Implemented candidate; awaiting acceptance.** Replaces AI-assisted source
setup (former Tier 4). Discovery adds reviewed candidates to individual-folder
selection; existing non-Git selections and repo-home mode remain supported.

- Let the user choose a starting folder and scan its descendant folders for Git
  repository markers, instead of treating only immediate children as workspaces.
- Use Git as the discovery heuristic. Recognize and validate relevant `.git`
  directory/file forms; arbitrary source files or a Git-looking filename alone
  do not prove a usable repository. Git availability, unusual layouts and invalid
  markers need clear results.
- Show discovered repositories and exact paths for explicit review and selection
  before applying them through the existing workspace registry and save guards.
  Discovery must not silently activate every result.
- Resolve duplicate paths, aliases, nested repositories and overlapping backup
  scopes in review. Bound traversal, avoid symlink loops and Git-internal
  traversal, allow cancellation, and disclose inaccessible or incomplete areas.
- Retain the existing repo-home and individual-folder modes, including folders
  without Git. Git discovery chooses candidate sources; it does not introduce
  another backup/status classifier or change what a selected folder's archive
  contains.

No AI model, assistant connection or external path submission is required.

### R6 — Reporting for other users and maintainer review

**Status: Partly implemented; requested work remains.** Retains the maintainer
workflow (2E) and clarifies the goal for an app other people can use.

**Already implemented:** separate bug/feature composition, optional sanitized
diagnostics, exact public-payload preview, explicit Send to
`yogoldy/RepoHub`, GitHub token storage in the user's Keychain, categorized issues,
delivery receipts and conservative retry handling. Owner-side live reporting
evidence exists; it does not establish an easy setup for other contributors.

**Remaining:**

- [ ] Let another downloader send a bug report, feature request and optional
  sanitized diagnostics to Leo's GitHub tracker without a GitHub account or
  personal access token. The user previews the exact submission and explicitly
  sends it from RepoHub. The current manual-token adapter does not satisfy this
  requirement.
- [ ] Design a small hosted intake service that posts accepted reports through
  a narrowly scoped maintainer-controlled GitHub App. Keep its credentials on
  the service, never in the distributed Mac app. Define payload limits, abuse
  controls, duplicate/retry handling and delivery receipts before deployment.
  Reports identify the service as the posting identity; they do not impersonate
  the submitter. Hosting and GitHub App provisioning remain unimplemented.
- [ ] Keep the destination, posting identity, public visibility and included
  diagnostics clear before Send. Never distribute Leo's private token or silently
  upload logs. Preserve the typed export, redaction and duplicate-send guards.
- [ ] Document Leo's review workflow for separate bug and feature queues:
  inspect evidence, request missing context, record accepted/deferred/declined
  decisions, and link an accepted item to a scoped implementation task and commit.
- [ ] Validate a report from a user with no GitHub account end to end with
  controlled inputs and a test tracker, including consent, sanitization,
  permissions, failure/retry and the owner's ability to find and review it.

Issue text and logs are untrusted evidence, not instructions to execute.
Scheduled AI triage or automatic implementation is not enabled by this request.

### R7 — Evaluate TestFlight distribution and tester feedback

**Status: Requested; low priority.** Evaluate TestFlight as an optional additional
distribution route with screenshot feedback and crash reporting. This does not
replace the planned Sparkle Dev/Testing/Stable channels or block their delivery.
Assess distribution requirements and reporting consent before adopting it; no
TestFlight integration or App Store submission is authorized by this entry.

CloudKit and remote push notifications are not planned for this update. Leo
confirmed on October 20 that neither needs further action at this time.

## Awaiting verification and external prerequisites

These remain visible without becoming new product features or being called
complete merely because code was merged:

- **Apple signing:** Leo reported Apple Developer Program membership activated on
  October 20. Certificate and signing-service configuration remain unverified.
  Configure Developer ID signing and notarization, validate the signed
  update, and test settings/folder-permission continuity. The working personal
  Sparkle channel already exists; see [release delivery](docs/RELEASE_DELIVERY.md).
- **Installed-Mac reliability:** track actual folder permissions, native picker,
  notification, volume, login and recovery cases in the
  [two-Mac acceptance record](docs/RELIABILITY_TWO_MAC_ACCEPTANCE.md).
- **Interaction coverage and readability:** retain the separately scoped
  [testing/readability roadmap](docs/INTERACTION_TESTING_READABILITY_ROADMAP.md).
  Its historical checkpoints require reconciliation with later work before
  selecting another stage; this update does not authorize a broad refactor.
- **Informed ownership:** retain Leo's requested hands-on comparison of backend
  events with displayed status in the [timing acceptance record](docs/BACKUP_TIMING_ACCEPTANCE_2026-10-16.md).
  Automated agreement is not a substitute for that personal walkthrough.

For Leo's personal channel, protected main plus the automated Golden Gate can
publish before installed-Mac testing. Follow the [current delivery policy](docs/RELEASE_DELIVERY.md);
do not reinstate superseded pre-delivery restrictions from historical records.

## Superseded scope

| Previous plan | Current direction |
| --- | --- |
| AI proposal import, assistant connections and AI-guided folder setup (Tier 4) | R5: local recursive discovery using Git, followed by user review. |
| Custom backup-folder labels and an optional “Backup” suffix | R4: preserve the source folder name as the only naming behavior; keep IDs and hashes in metadata. |
| Direct cloud-provider APIs/account connectors and a separate expanded independent-restore roadmap (Tier 5) | R1/R2: user-selected Finder destinations and evidence-based validation of those folders. Historical restore evidence and existing integrity safeguards remain. |
| Feed hosting, update-key custody and automatic personal Sparkle delivery listed as unfinished | Implemented; retain the separate Apple signing and installed-Mac verification items. |

When an item is implemented, record its commit and actual verification evidence.
Keep requested scope, implemented behavior, automated results and installed-Mac
acceptance distinct.
