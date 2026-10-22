# RepoHub product roadmap

RepoHub should make it easy to answer: **Are my chosen repos safely backed up,
and what needs my attention?** The menu bar is the everyday view.

The goal is an open-source application that other people can understand and use
reliably. "Productizable" refers to usable setup, clear explanations, coherent
UI, meaningful diagnostics, continuous integration and stable update delivery;
it is not a monetization requirement. These are continuing product principles,
not a separate redesign or an instruction to add unnecessary infrastructure.
The repository is public. License selection remains an owner decision: GitHub
reported no detected license and no project license file was found on October 20.

## Scope and status — updated October 20, 2026

This is the current reference for Leo's unfinished product requests. It supersedes
the previous tiered roadmap at source
`38d354d5ade1cc5664c43a15cb680bc31b0d0019`; Git retains that version and its
implementation history. Leo approved the revised scope below on October 17 and
consolidation of the testing roadmap into this reference on October 20.
Leo reconfirmed the eleven-step delivery proposal as the canonical roadmap;
it retains his subsequent decision to put account-free reporting before other
Finder sync-folder providers. Older proposals do not define a separate queue.

- **Requested:** agreed product direction, with implementation still pending.
- **Implemented:** code exists; this does not imply every installed-Mac condition
  has been verified.
- **Awaiting verification:** the remaining work is evidence or acceptance rather
  than a new feature.
- **Superseded:** removed from the active roadmap by Leo's revised direction.

The sequence below records the current intended order. Roadmap entries do not
by themselves start feature implementation, authorize external submissions,
or authorize a Git push.
Complete approved work in scoped commits with proportionate tests and evidence.

## Next delivery sequence

The first signed Dev release, `0.0.9` / build 9, was published and installed on
the Pro on October 22 from `a9b3895f36a4c76ac68882863baf1ffae26a4d43`.
Its 77-test focused Dev gate, native build, Apple notarization, stapling,
Gatekeeper and independent downloaded-archive signature checks passed. The app
and helper report that exact build/source; six protected configuration files
retained their pre-install hashes. Stable remains build 7; the Air is untouched.
See the [live Dev checkpoint](docs/UPDATE_CHANNELS.md#live-dev-checkpoint--october-22-2026)
and earlier [unpublished signing record](docs/RELEASE_DELIVERY.md#unpublished-signing-validation--october-20-2026).

The ad-hoc-to-Developer-ID transition requested Desktop access again; Leo granted
it. This establishes initial consent, not permission continuity across a future
signed update. The helper listed all 15 configured sources without permission
errors; content verification and the broader native acceptance remain separate.
The Pro's local experimental opt-in is enabled; after the explicit Settings save,
native evidence reports Dev and Sparkle reports no newer update. The Testing feed,
subsequent Sparkle update, Air acceptance and Stable promotion remain pending.

**Immediate work, before another Dev publication:** the local Keychain publishing
wrapper is implemented with one-time hidden input, signed helper verification,
existing-key continuity checks and credential-free focused tests before release.
It reuses the staged Dev publisher and needs no per-release pasted secrets.
Provisioning with real credentials still needs Leo's secure Terminal entry.
Keychain authorization prompts may still occur. The app/helper signing-identity
guard is also implemented and matches installed build 9; a subsequent signed
Sparkle update must still prove permission continuity. See
[local Dev publishing](docs/LOCAL_DEV_PUBLISHING.md) for setup, guards and limits.

The installed Dev candidate also addresses [issue #14](https://github.com/yogoldy/RepoHub/issues/14):
a backup deferred by actively changing source files no longer leaves a generic
failure overriding later Rescan now results. Attempt history and genuine errors
remain visible. GR02 covers manual-scan recovery and archive preservation; this
fix still requires installed acceptance after delivery.

Updating this roadmap is already handled here; it is not an additional
prerequisite or a numbered development stage. This sequence replaces the old
interaction-testing plan. Existing controller, API, native and release coverage
remains evidence within its original limits; installed acceptance is separate.

1. **Implement Dev → Testing → Stable channels.** Dev provides quick delivery
   to opted-in Macs after focused tests, a native build and package/signature
   checks. Testing requires the full automated gate; Stable requires installed
   acceptance and Leo's explicit promotion approval. Dev must not replace the
   stable feed or public latest download. Record source identity, monotonic build
   numbering and channel-switch behavior. The updater, local publisher, Testing
   workflow, diagnostics and policy are implemented together in the current local
   branch candidate. The Dev feed is live and build 9 is installed on the Pro; the
   Testing feed and subsequent updater acceptance remain pending. See the
   [channel contract](docs/UPDATE_CHANNELS.md) for commands and acceptance limits.
   Existing protected-main requirements remain in force.
   **Ordinary-user offer isolation:** ordinary installations follow Stable and
   keep experimental controls out of their normal settings flow. Deliberately
   enable Dev/Testing locally on Leo's Pro and Air. Public feeds/packages and
   deliberate advanced access by others are acceptable; do not add private
   repositories, authentication services or hardware restrictions. Validate
   Stable defaults, explicit test enablement, persisted preference behavior,
   exact-channel update offers, diagnostic agreement and byte-identical Stable
   promotion. The clarified UI/enablement behavior is implemented locally with
   isolated native/controller/diagnostic regressions. The Pro opt-in is enabled;
   its guarded saved Dev selection and a no-newer-update check are observed.
   Subsequent update acceptance and Air enablement/acceptance remain pending.
2. **Configure consistent Developer ID signing and notarization.** Use a
   consistent app/helper identity across channels; verify signed components,
   hardened runtime, notarization and stapling. Test the existing ad-hoc app's
   transition without claiming that signing grants folder access. Membership
   is active per Leo. A valid Developer ID Application identity, the required
   GitHub secret names and read-only notarization authentication are verified.
   The unpublished GitHub signing/notarization package test passed on source
   `49462f18482093ea380ccbaafe5a686db5d75ac7`. The first signed Dev bootstrap is
   installed with renewed Desktop consent; subsequent-update permission
   continuity remains unverified.
3. **Deliver a Dev build to the Pro, including local commit `82b1a85`.** Confirm
   setup stays inside the menu-bar panel, dismissal/reopening retains drafts,
   and picker choose/cancel returns to the same step. Exercise repo selection,
   navigation, Finder shortcuts, status explanations, default/per-repo settings
   Save/Cancel, Back up now and Rescan now. Check the visible Show me folder
   highlight, its reset, repeated/repo-switched activation, keyboard and reduced
   motion, without opening Finder or modifying settings as a demo side effect.
4. **Test permission and failure recovery on the Pro.** Use isolated fixtures
   and an isolated identity/account for disruptive cases: actual folder-access
   refusal/grant/revocation/restart, optional notification permission lifecycle,
   helper interruption/reconnection, stale status, unreadable roots/nested files,
   destination denial and volume disappearance/substitution/remount. Preserve
   configuration, IDs, schedules and previous verified archives; compare native
   display, helper observations and diagnostics. Never reset daily permissions.
5. **Save useful visual regressions and run the full Testing gate.** Add checks
   for concrete gaps alongside existing controller/API/native coverage. Use
   synthetic data and isolated settings; select tools for the needed behavior,
   rather than making a particular browser MCP installation a prerequisite.
   Controlled failures must fail the gate. Browser checks do not establish actual
   macOS permission or Finder behavior.
6. **Deliver another signed update to the Pro.** Verify permission/configuration
   continuity across an update, app/helper versions, channel eligibility and
   recovery. A successful initial installation does not establish update safety.
7. **Test installation and a subsequent update on the Air.** Verify onboarding,
   helper-observed access, native pickers, backup hashes and actual upload
   observations on the same candidate package. Preserve the Air's own settings;
   use an isolated account/identity for fresh-install conditions. Exercise the
   complete CI/distribution/install/update loop, with explicit evidence for each
   host and cleanup of owned test services. A fix creates a new candidate whose
   affected acceptance checks must be rerun.
8. **Promote the accepted package to Stable.** Require the Testing gate, recorded
   installed results and Leo's approval. Promote the tested package without an
   untested rebuild; follow protected-main checks and record source/package
   identity, version and recovery options.
9. **Implement account-free reporting and maintainer review (R6).** Users
   preview and explicitly send sanitized diagnostics without a GitHub account;
   a hosted service posts to Leo's tracker with server-held credentials. Establish
   this feedback path before expanding provider-specific behavior.
10. **Support other Finder sync-folder destinations (R2).** Test provider
    placeholders, access, disappearance/recovery and preservation. Keep local
    verification distinct from confirmed remote upload.
11. **Evaluate TestFlight (R7; low priority).** Consider tester feedback and crash
    reporting after the Sparkle workflow is established.

Readability standards remain current. Broad cleanup and Leo's representative
AI-teacher review are deferred and require separate scope approval; they do not
block channels or signing. CloudKit, remote push notifications, Tailwind and
TestSprite evaluation remain deferred. Update commands, links and coverage claims
as each step lands; do not retain a competing release order in historical guides.

## Implemented foundation and pending local follow-up

The previous local update batch shipped through releases 0.0.5–0.0.7. The
setup-panel follow-up `82b1a85` is committed locally, not pushed or installed;
native opening/dismissal and picker-return acceptance remain in step 3 above.

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
  boundaries. These controls were delivered in the first-run setup release batch.
- [x] **Prominent scan and backup controls:** Back up now and Rescan now share
  equal-width gold buttons with distinct circular-arrow/scan icons. Repository
  Backups is a full-width navigation row with a folder icon, white label, trailing
  chevron and subtle hover fill, followed by notifications. The footer keeps only
  the last-check time and Quit. Scan requests preserve the icon through pending
  and failed requests. This is a local presentation change, not a new backup rule.
- [x] **First-run setup:** the approved five-step welcome flow,
  one iCloud destination, readable folder layouts, reviewed Git discovery and
  recoverable configuration saves are integrated. The first protected release
  passed the clean gate and installed migration; draft reload, discovery
  cancellation and selected-destination Finder corrections shipped in 0.0.6 and
  0.0.7. See [the implementation record](docs/FIRST_RUN_SETUP.md). The local panel
  host change remains separately pending above.

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

**Status: Implemented and installed on the Pro in the 0.0.5–0.0.7 release batch.** Selects one
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

**Status: Setup implemented and installed; local panel follow-up awaits native
acceptance.** The five-step welcome flow supports fresh setup and an existing
user's prefilled review without changing configuration before explicit apply.
This does not close the separate walkthrough/Show me interaction checks in
step 3 above. See [first-run setup](docs/FIRST_RUN_SETUP.md).

Explain sources, destination, schedules, manual backup, verification and upload
status through a short visual walkthrough tied to actual controls. Offer Skip,
Back, Next and replay from Settings, keyboard support and reduced motion.
Demonstrations must be recognizable as demonstrations and must not change settings
or start backups. Preserve existing users' configuration and avoid forcing the
tutorial on every launch.

### R4 — Preserve repo names in backup folders

**Status: Implemented, with installed Pro migration/hash/upload evidence.** Revised by Leo on October 18: one naming behavior,
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

**Status: Implemented, with installed Pro discovery/cancel/reload evidence.** Replaces AI-assisted source
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

- **Apple signing:** the unpublished exact-source GitHub test verified usable
  certificate-export decryption, Developer ID packaging, Apple notarization,
  stapling, Gatekeeper acceptance and independent archive signature verification.
  Live channel delivery and the installed transition, including settings/folder
  permissions and subsequent-update continuity, remain pending. The existing
  public release and release-mode variable were unchanged; see the
  [signing validation record](docs/RELEASE_DELIVERY.md#unpublished-signing-validation--october-20-2026).
- **Installed-Mac reliability:** track actual folder permissions, native picker,
  notification, volume, login and recovery cases in the
  [two-Mac acceptance record](docs/RELIABILITY_TWO_MAC_ACCEPTANCE.md).
- **Interaction coverage and readability:** interaction checks are integrated
  into steps 3–7 above. The [readability standards](docs/READABILITY_STANDARDS.md)
  remain current; representative teacher review and broad cleanup are deferred,
  rather than prerequisites for this release sequence.
- **Informed ownership:** retain Leo's requested hands-on comparison of backend
  events with displayed status in the [timing acceptance record](docs/BACKUP_TIMING_ACCEPTANCE_2026-10-16.md).
  Automated agreement is not a substitute for that personal walkthrough.

Protected main plus the full Golden Gate may publish to Testing before installed
acceptance. Stable requires explicit approval and recorded Pro/Air results.
Follow the [current delivery policy](docs/RELEASE_DELIVERY.md); do not apply the
superseded automatic-Stable policy from historical records.

## Superseded scope

| Previous plan | Current direction |
| --- | --- |
| Separate nine-stage interaction/testing roadmap | This document's delivery sequence incorporates its remaining interaction and recovery checks; readability standards remain current and broad cleanup is deferred. |
| AI proposal import, assistant connections and AI-guided folder setup (Tier 4) | R5: local recursive discovery using Git, followed by user review. |
| Custom backup-folder labels and an optional “Backup” suffix | R4: preserve the source folder name as the only naming behavior; keep IDs and hashes in metadata. |
| Direct cloud-provider APIs/account connectors and a separate expanded independent-restore roadmap (Tier 5) | R1/R2: user-selected Finder destinations and evidence-based validation of those folders. Historical restore evidence and existing integrity safeguards remain. |
| Feed hosting, update-key custody and automatic personal Sparkle delivery listed as unfinished | Implemented; retain the separate Apple signing and installed-Mac verification items. |

When an item is implemented, record its commit and actual verification evidence.
Keep requested scope, implemented behavior, automated results and installed-Mac
acceptance distinct.
