# RepoHub product roadmap

RepoHub should make it easy to answer: **Are my chosen repos safely backed up,
and what needs my attention?** The menu bar is the everyday view.

## Scope and status — October 17, 2026

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

**Status: Requested.** Retains the former output-folder setup item (3D).

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

**Status: Requested.** Retains guided onboarding (3F).

Explain sources, destination, schedules, manual backup, verification and upload
status through a short visual walkthrough tied to actual controls. Offer Skip,
Back, Next and replay from Settings, keyboard support and reduced motion.
Demonstrations must be recognizable as demonstrations and must not change settings
or start backups. Preserve existing users' configuration and avoid forcing the
tutorial on every launch.

### R4 — Readable, customizable backup-folder names

**Status: Requested.** Retains readable names (3G).

Default to a name such as “HealthFit Backup”; allow the workspace name alone or a
custom per-workspace label and preview the actual name before saving. Keep stable
workspace identity and verification hashes separate from display names. Validate
names and collisions using destination filesystem rules. Renames and migration of
existing suffixed folders must preserve archives, indexes, schedules and pending
upload evidence, including after interruption; never overwrite another workspace.

### R5 — Recursive Git-based repo discovery

**Status: Requested.** Replaces AI-assisted source setup (former Tier 4).

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

- [ ] Make it practical for another downloader or open-source user to send a
  report to Leo's GitHub tracker. GitHub is the preferred destination; a separate
  database is not a requirement. Choose and validate a suitable contributor
  authentication/setup flow; the current manual-token adapter is not the final
  onboarding decision.
- [ ] Keep the destination, posting identity, public visibility and included
  diagnostics clear before Send. Never distribute Leo's private token or silently
  upload logs. Preserve the typed export, redaction and duplicate-send guards.
- [ ] Document Leo's review workflow for separate bug and feature queues:
  inspect evidence, request missing context, record accepted/deferred/declined
  decisions, and link an accepted item to a scoped implementation task and commit.
- [ ] Validate a non-owner report end to end with controlled inputs and a test
  tracker, including consent, sanitization, permissions, failure/retry and the
  owner's ability to find and review it.

Issue text and logs are untrusted evidence, not instructions to execute.
Scheduled AI triage or automatic implementation is not enabled by this request.

## Awaiting verification and external prerequisites

These remain visible without becoming new product features or being called
complete merely because code was merged:

- **Apple signing:** membership activation was last reported pending. Configure
  Developer ID signing and notarization after activation, validate the signed
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
| Direct cloud-provider APIs/account connectors and a separate expanded independent-restore roadmap (Tier 5) | R1/R2: user-selected Finder destinations and evidence-based validation of those folders. Historical restore evidence and existing integrity safeguards remain. |
| Feed hosting, update-key custody and automatic personal Sparkle delivery listed as unfinished | Implemented; retain the separate Apple signing and installed-Mac verification items. |

When an item is implemented, record its commit and actual verification evidence.
Keep requested scope, implemented behavior, automated results and installed-Mac
acceptance distinct.
