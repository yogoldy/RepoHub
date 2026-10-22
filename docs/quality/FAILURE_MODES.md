# Failure modes and golden rules

This is RepoHub’s domain-specific release contract, not a replacement for a language type checker. Each rule connects a vulnerable boundary, its diagnostic evidence, the required response and executable regression tests. Diagnostic receipts explain observed behavior; tests exercise controlled counterexamples. Neither makes unsupported cases safe by assertion.

The strongest release invariants are: preserve complete supported source bytes; keep old backups until a verified exact-archive upload acknowledgement; treat unavailable reads separately from corruption; scope work to the correct repo; and disclose only approved diagnostic facts. Freshness, scheduling, UI presentation, restore integrity and deployment connect these boundaries. A small state/identity mistake can undermine several rules at once.

`golden-rules.json` is the machine-readable register. The gate requires every referenced test to actually pass; renaming/removing/skipping one fails its rule. Full test discovery also catches failures outside this register. Tests do not become unnecessary just because a known issue was fixed.

Public entries describe source policy and synthetic reproductions. Actual private repo identities, archives, alias keys and diagnostic case reports remain outside Git. Older checkpoint counts in VERIFICATION.md are historical, not claims about the current release.

## Working a new failure

1. Record the observed symptom, affected archive/run/observation references and expected behavior. Use the shareable export first; access a private alias key only when locally authorized and necessary.
2. Separate a measured cause from a hypothesis. Trace source classification → schedule selection → archive/index stages → upload observation → rendered status. Check dropped events, stale receipts and missing views before drawing conclusions.
3. Reproduce with an isolated small fixture. Make a failing test before fixing the policy; preserve failed receipts privately. Never use personal source files as fault-injection targets.
4. Apply the narrow fix, test recovery as well as failure, and add/update a rule with the exact test ID and remaining limits. A green test is not a reason to erase the incident or its uncertainty.
5. Run the release gate and required manual checks. Keep the evidence tied to the exact source revision. Do not carry a previous version’s passing receipt forward as new evidence.

## Rule register

### Menu bar appearance must reuse repository presentations

The menu bar previously interpreted raw `needs_backup` and verification fields
separately from the cards. That missed the approved Finder-only backed-up
exception. Menu-bar counts now aggregate the existing `RepoStatus.present` results;
Swift executes that same shipped policy in the owned WebKit page. It contains no
repository-state classifier. The waiting count includes existing backup-pending
statuses; confirmed changes count the existing confirmed file/Git/metadata labels.
First backups and unclassified differences are not confirmed changes.

The preference is stored per Mac in the app's UserDefaults only after Save changes.
Navigation guards unsaved drafts, conflicts preserve them, and a pending save
cannot be duplicated or interrupted. Native bridge requests retain exact-page,
main-frame, fixed-mode and request-ID checks. The logo is unchanged.

`menu_bar_presented` records a bounded mode, count and symbol read back after the
native title is set. Independent diagnostics reuse the existing status oracle to
detect wrong counts or symbols; `menu_bar_disagreement` is a failure, not evidence
that the cards themselves changed. Exports contain fixed enums and capped counts,
never tooltip prose. GR06 and GR22 register the regression tests. Browser preview
cannot save native preferences. Actual installed menu-bar layout and restart
acceptance remain required when this local candidate is delivered.

### Source-change recovery through Rescan now — issue #14, October 22, 2026

An installed build recorded `SourceChanged` as both `verification_deferred` and
`repo_backup_failed`. Rescan now refreshed verification, but the old backup
error still took precedence in the shared presentation and problem tracker.
This produced a persistent “Needs attention — failure” for retryable source
activity. Local evidence confirmed ongoing writes too; a scan cannot make an
actively written source stable or replace a backup.

The typed exception now records `backup.deferred` and a `verification_deferred`
event linked to the attempt's run/repo/archive. An otherwise successful run ends
as `deferred`; mixed genuine errors still end as `failed`. The current verification
becomes `changing`, which the existing shared renderer, diagnostics and menu-bar
aggregation already understand. No new readiness classifier, message matching,
source exclusions, schedule change or immediate backup retry is introduced.
The previous archive/index stay intact. The deferred attempt remains historical
when a later successful scan replaces the live verification state.

The isolated regression first failed on the original persistent error. It now
exercises the guarded `/api/scan` route through ongoing writes, matched contents
and newly detected edits, confirming no backup call or archive/index change.
Synthetic exact-archive upload evidence is explicit; it is not a real iCloud
observation. A second case retains a genuine permission failure beside a
source-change deferral after rescan, including the menu warning. Typed export
keeps the deferred reason and attempt history. Both tests are registered in GR02
and discovered by the existing GitHub workflow/full gate and focused Dev suite.
Installed/native acceptance of this local fix remains pending delivery; the
running installed helper is unchanged.

### GR01 — Preserve complete contained workspace bytes

**Susceptible boundary:** Hidden, ignored and uncommitted files silently omitted; archive member handling loses directories or modes.

**Cause / solution:** Git status is not a file inventory. Archive contained filesystem entries and verify their contents before publication.

**Required behavior:** Include ignored/uncommitted bytes and ordinary contained Git history; do not follow external links.

**Diagnostic trail:** `archive_stage`, `archive_verified`, `repo_backup_finished`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_hub.HubTests.test_complete_archive_includes_hidden_ignored_and_symlink_without_following`
- `test_hub.HubTests.test_archive_content_verification_includes_hardlinks_and_empty_directories`
- `test_scoped_backups.ScopedBackupTests.test_appledouble_and_hidden_ignored_files_are_still_protected`

**Remaining exposure:** Live databases and unsaved application memory are not atomic snapshots. External Git directories/worktrees/submodules require explicit support.

### GR02 — Hashes decide meaningful changes

**Susceptible boundary:** Equal-size edits restore their mtime, or source content changes during archive construction.

**Cause / solution:** Metadata is only a scheduling hint. Hash content; compare source before/after and verify archived members.

**Required behavior:** Reject unstable snapshots; preserve old backups; detect same-size/same-mtime edits. Source changes during verification appear as “Files changing,” with another check on the next scan and a scoped menu-bar retry. Archive mutation or corruption remains an error. A scoped retry never creates an archive or refreshes the global scan timestamp.

**Diagnostic trail:** `repo_checked`, `archive_stage`, `repo_backup_failed`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_hub.HubTests.test_same_size_same_mtime_edit_is_detected_and_replaced`
- `test_hub.HubTests.test_timestamp_only_changes_match_hashes_and_do_not_replace_backup`
- `test_hub.HubTests.test_metadata_preserving_change_during_snapshot_is_rejected`
- `test_hub.HubTests.test_source_mutation_is_transient_and_retry_is_scoped`
- `test_hub.HubTests.test_archive_mutation_is_not_source_mutation`
- `test_hub.HubTests.test_change_during_backup_does_not_publish`

**Remaining exposure:** Concurrent writes can force retries. No filesystem snapshot or transactional database capture is provided.

**Hosted-test lesson:** CI exposed Git background maintenance removing `objects/maintenance.lock` between inventory and hashing in a restore fixture. All committing unit-test fixtures now disable automatic maintenance/GC before committing; the same background writer also changed a read-only monitoring fixture. Production concurrent-write rejection remains intact; an idle synthetic fixture must not silently depend on the runner’s Git defaults.

### GR03 — Finder-only hints cannot cause broad replacements

**Susceptible boundary:** Repeated .DS_Store writes look like edits; a whole-schedule check rebuilds unchanged repos.

**Cause / solution:** Classify Finder/Git/project differences separately; ignore only ordinary .DS_Store trigger changes while retaining honest full-match status.

**Required behavior:** No replacement for Finder-only writes; build only selected meaningfully changed/new/damaged repos.

**Diagnostic trail:** `repo_checked`, `schedule_decision`, `archive_reused`, `repo_backup_finished`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_scoped_backups.ScopedBackupTests.test_repeated_finder_writes_do_not_replace_archives_or_rewrite_cloud_index`
- `test_scoped_backups.ScopedBackupTests.test_only_meaningfully_changed_repo_gets_archive_when_schedule_checks_every_repo`
- `test_scoped_backups.ScopedBackupTests.test_targeted_backup_cannot_copy_another_repo_even_if_it_changed`
- `test_scoped_backups.ScopedBackupTests.test_finder_exception_cannot_hide_corrupt_archive`

**Remaining exposure:** Other metadata such as AppleDouble remains protected. Never generalize this exception to arbitrary hidden files.

### GR04 — Unavailable verification is not corruption

**Susceptible boundary:** iCloud placeholders/timeouts/permissions produce read failures and can trigger unnecessary rebuilds.

**Cause / solution:** Separate OSError availability from checksum/archive-format failures; defer unavailable reads instead of rebuilding.

**Required behavior:** Keep index/archive intact on unavailable reads, disclose the failure, then reuse or replace after recovery.

**Diagnostic trail:** `verification_deferred`, `repo_backup_failed`, `archive_repair_needed`, `archive_reused`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_scoped_backups.ScopedBackupTests.test_unavailable_archive_is_reported_without_replacement_and_recovery_reuses_it`
- `test_scoped_backups.ScopedBackupTests.test_read_failure_defers_changed_repo_until_verification_can_recover`
- `test_hub.HubTests.test_corrupted_archive_detected_and_repaired`

**Remaining exposure:** Conservative deferral also delays genuinely changed sources. Other RuntimeError classifications and real provider races remain review points.

### GR05 — Retain old backup until exact replacement is safe

**Susceptible boundary:** Copy/index errors, stale cloud receipts or 100% progress lead to premature deletion.

**Cause / solution:** Persist a verified replacement; gate pruning on fresh acknowledgement for its exact archive identity.

**Required behavior:** Never prune on progress alone, missing/old receipts or failed publication; preserve unknown/legacy files.

**Diagnostic trail:** `archive_verified`, `retention_decision`, `retention_verified`, `prune_started`, `prune_finished`, `retention_failed`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_hub.HubTests.test_failed_replacement_preserves_previous_copy`
- `test_hub.HubTests.test_old_copy_kept_until_replacement_upload_is_confirmed`
- `test_hub.HubTests.test_progress_and_retry_error_do_not_confirm_or_prune`
- `test_hub.HubTests.test_index_publication_failure_keeps_old_copy_and_retries_cleanup`
- `test_policy_health.SettingsHTTPTests.test_stale_upload_receipt_keeps_previous_backup`

**Remaining exposure:** Network outage, quota exhaustion and full-disk behavior need controlled live fault runs; mocked transitions are not provider guarantees.

### GR06 — Display decisions need fresh evidence

Post-sleep recovery can briefly leave scan/hash evidence stale while the helper
catches up. Treating that wait as “can’t get current backup status” sounded like
a failed backup. Policy `status-clarity-7` uses “Waiting for fresh checks” and
“Waiting for fresh backup status.” The underlying stale phase, false readiness,
freshness thresholds and persistent-problem notifications are unchanged. The
summary describes missing fresh status rather than implying every backup is lost.
Technical details retain the observed reasons; the display does not claim sleep
caused a particular case without evidence. Old policy wording remains valid for
historical receipts.

The menu's Rescan now uses the existing guarded `/api/scan` endpoint. Acceptance
means a request was accepted, not that the scan or a backup completed. The actual
controller test covers fresh tokens, duplicate requests and failed requests; an
isolated HTTP regression verifies origin/Host/token guards, a real forced scan,
preserved archive bytes/index and no call to backup. Actual card/detail mutations
and stale-to-fresh recovery remain subject to the independent diagnostic oracle.
Private sleep/diagnostic case records remain outside Git.

**Susceptible boundary:** Green check uses old archive data, stale hashes, missing upload flags or an unavailable helper.

**Cause / solution:** Use the shared status policy and join archive/observation/run identities; revoke stale/failed receipts.

**Required behavior:** Green requires fresh content verification plus exact-archive upload acknowledgement. Display policy 5 also permits the ordinary .DS_Store-only exception when project files and Git match. Keep the raw different comparison and Finder-only reason; absent view receipts do not prove agreement.

**Diagnostic trail:** `status_repo`, `ui_presented`, `presentation_input_disagreement`, `presentation_disagreement`, `upload_stale`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_hub.HubTests.test_failed_cloud_probe_revokes_previous_confirmation`
- `test_hub.HubTests.test_upload_unknown_false_conflict_and_error_never_confirm_success`
- `test_backup_lifecycle.LifecycleTests.test_green_icon_with_missing_upload_is_logged_as_input_disagreement`
- `test_change_evidence.EvidenceTests.test_no_record_of_second_view_is_not_claimed_as_agreement`
- `test_change_evidence.EvidenceTests.test_both_views_are_correlated_and_disagreement_is_reported`

**Remaining exposure:** Rendered progress percentages, selected-card visibility, pixels and clickability still lack full diagnostic acceptance coverage.

### GR07 — Schedule and power policy stay per repo

**Susceptible boundary:** A power transition pauses incorrectly, resets unrelated timers or starts all repos after one edit.

**Cause / solution:** Track effective per-repo settings and cadence; recheck power before automatic work and preserve unattempted clocks.

**Required behavior:** Battery defaults have no after-edit backups; manual-only works; a selected automatic plan cannot force unrelated repos.

**Diagnostic trail:** `schedule_decision`, `backup_deferred`, `backup_paused`, `backup_finished`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_policy_health.PolicyTests.test_battery_default_is_no_after_edits_and_manual_only_is_supported`
- `test_policy_health.SettingsHTTPTests.test_after_edit_plan_only_archives_selected_repo`
- `test_policy_health.SettingsHTTPTests.test_power_change_finishes_current_archive_and_stops_next_repo`
- `test_policy_health.SettingsHTTPTests.test_partial_automatic_run_does_not_advance_unattempted_repo_clock`
- `test_policy_health.SettingsHTTPTests.test_repo_cadence_survives_restart_and_only_backs_up_due_repo`

**Remaining exposure:** Physical battery transitions, full sleep/wake and logout/login cycles still require hardware smoke tests.

### GR08 — Diagnostics cannot break or mutate backups

**Susceptible boundary:** Full disk, partial records, rotation or logging recursion stops backups or produces fake edits.

**Cause / solution:** Bound private JSONL storage; tolerate write loss; exclude diagnostics from monitored/saved data. Record unobserved gaps honestly.

**Required behavior:** Backup operation survives log failure; malformed records are bounded; diagnostic activity creates no backup changes.

**Diagnostic trail:** `heartbeat`, `runtime_gap`, `helper_started`, `backup_interrupted`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_diagnostics.DiagnosticTests.test_full_disk_failure_recovers_and_records_loss`
- `test_diagnostics.DiagnosticTests.test_partial_write_survives_restart_without_poisoning_next_event`
- `test_diagnostics.DiagnosticTests.test_logging_failure_does_not_stop_backup_or_enter_backup_data`
- `test_change_evidence.EvidenceTests.test_diagnostic_activity_does_not_create_repo_or_saved_data_changes`
- `test_backup_lifecycle.LifecycleTests.test_restart_discloses_incomplete_run_without_claiming_recovery`

**Remaining exposure:** The app cannot observe while powered off. Missing records are evidence gaps, not successful recovery.

### GR09 — Shared diagnostics have an explicit type contract

**Susceptible boundary:** A new log field, raw error, nested payload or exact timestamp leaks through the export.

**Cause / solution:** Use separately reviewed field-specific enums/types, fresh aliases and bounded relative measurements; reject unknown events and values.

**Required behavior:** No names/paths/raw hashes/arbitrary text/exact dates/exact sizes; exclude private alias key from previews.

**Diagnostic trail:** `verification_deferred`, `repo_checked`, `ui_presented`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_diagnostic_export.ExportTests.test_enums_are_field_specific_and_not_a_global_word_list`
- `test_diagnostic_export.ExportTests.test_unknown_events_and_unknown_nested_fields_fail_closed`
- `test_diagnostic_export.ExportTests.test_no_wall_clock_raw_sizes_hashes_or_free_text`
- `test_diagnostic_export.ExportTests.test_adversarial_types_and_huge_numbers_do_not_escape_or_crash`
- `test_diagnostic_export.ExportTests.test_namespaces_are_fresh_and_relative_order_preserved`
- `test_report_preview.ReportPreviewTests.test_bug_has_exact_share_files_and_private_local_draft`

**Remaining exposure:** Operational patterns remain bounded facts. User-written report prose is separate; a preview and confidentiality reminder cannot guarantee it contains no personal information.

### GR10 — Local HTML APIs cannot widen filesystem access

**Susceptible boundary:** Untrusted origin/frame/path or stale JSON revision changes files outside its scope.

**Cause / solution:** Keep loopback Host/Origin/token and revision guards; resolve allowed paths; native bridge accepts fixed actions and valid repo IDs.

**Required behavior:** Reject cross-origin and arbitrary path/payload requests; report previews cannot redirect their destination.

**Diagnostic trail:** `presentation_input_disagreement`, `runtime_error`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_hub.HubTests.test_http_json_conflicts_origin_host_and_view_boundaries`
- `test_hub.HubTests.test_data_and_views_cannot_escape`
- `test_report_preview.ReportPreviewTests.test_http_preview_requires_existing_origin_and_token_checks`
- `test_report_preview.ReportPreviewTests.test_bad_inputs_and_destination_injection_rejected`

**Remaining exposure:** Credential-backed GitHub delivery and other cloud destinations are unimplemented and need their own threat model/tests.

### GR11 — Restore audit must independently verify every supported entry

**Susceptible boundary:** Archive corruption/path traversal, input mutation or receiving umask hides a broken restore.

**Cause / solution:** Use an independently captured manifest, trusted input identities, safe isolated extraction and Git fsck/history checks. Explicitly restore link modes without changing targets.

**Required behavior:** Reject bad identities/unsafe paths/input mutations and compare full manifest plus contained Git facts.

**Diagnostic trail:** `archive_verified`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_restore_audit.RestoreAuditTests.test_full_restore_with_ignored_uncommitted_git_and_log_receipts`
- `test_restore_audit.RestoreAuditTests.test_symlink_mode_survives_different_receiver_umask_without_changing_target`
- `test_restore_audit.RestoreAuditTests.test_corrupt_archive_and_wrong_manifest_identity_fail_before_extraction`
- `test_restore_audit.RestoreAuditTests.test_traversal_duplicate_extra_and_absolute_paths_are_rejected`
- `test_restore_audit.RestoreAuditTests.test_input_mutation_during_restore_is_reported`
- `test_restore_audit.RestoreAuditTests.test_restored_hooks_and_fsmonitor_are_not_executed`

**Remaining exposure:** Synthetic audit tests do not prove current iCloud delivery. Actual independent receive/restore needs two-device evidence and cannot validate restored app/macros semantics.

### GR12 — Installation and restart must load the tested release

**Susceptible boundary:** Missing runtime module/route, stale native web view or launch-job reload fails after copying new code.

**Cause / solution:** Validate package/asset dependencies; retain old runtime; restart existing registered jobs; verify installed hashes and helper build identity before considering deployment complete.

**Required behavior:** Compiled native sources and packaged modules/routes must agree; local diagnostics must disclose interrupted runs.

**Diagnostic trail:** `helper_started`, `backup_interrupted`, `heartbeat`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_backup_lifecycle.LifecycleTests.test_restart_discloses_incomplete_run_without_claiming_recovery`
- `test_backup_lifecycle.LifecycleTests.test_creation_reuse_and_render_reason_share_archive_run_identity`

**Remaining exposure:** Live install, rollback, login-item registration and per-device served UI checks remain manual. Native compilation alone does not prove launchd/iCloud integration.


### GR13 — A report sends only its exact consented payload once

**Susceptible boundary:** Timeouts, double-clicks, crashes, account switches or unsafe preview/destination changes can publish the wrong report or duplicate it.

**Cause / solution:** Freeze and hash the exact public preview; require explicit Send/account confirmation; persist sending before POST under a process-safe lock; reconcile ambiguous outcomes against exact authored issue bytes without automatically reposting. Credentials remain in native Keychain/backend memory.

**Required behavior:** Fixed product tracker and approved diagnostic text only. Durable exact-identity receipts, retained drafts, no background sending, no token/prose in operational logs or HTML credential handling.

**Diagnostic trail:** `report_delivery`, with report-local aliases and approved state/reason codes only. No titles, prose, account names, issue URLs or credentials.

**Regression tests:**

- `test_report_delivery.ReportDeliveryTests.test_exact_preview_receipt_and_repeat_send_never_duplicates`
- `test_report_delivery.ReportDeliveryTests.test_lost_post_response_recovers_existing_issue_without_second_post`
- `test_report_delivery.ReportDeliveryTests.test_absent_issue_after_ambiguous_send_is_not_permission_to_repost`
- `test_report_delivery.ReportDeliveryTests.test_process_interruption_leaves_durable_uncertain_identity`
- `test_report_delivery.ReportDeliveryTests.test_double_click_while_posting_is_serialized`
- `test_report_delivery.ReportDeliveryTests.test_client_cannot_change_destination_payload_or_consent`
- `test_report_delivery.ReportDeliveryTests.test_foreign_or_malformed_receipt_never_becomes_sent`
- `test_report_delivery.ReportDeliveryTests.test_delivery_diagnostics_contain_only_codes_and_aliased_identity`
- `test_report_delivery.ReportDeliveryTests.test_sender_api_uses_existing_origin_and_token_boundary`
- `test_report_labels.ReportLabelTests.test_issue_text_never_selects_other_labels_or_commands`
- `test_report_delivery.ReportDeliveryTests.test_failed_durable_intent_flush_cannot_start_a_post`

**Remaining exposure:** GitHub list visibility can lag creation; absent or changed issues after ambiguous POST remain unconfirmed, requiring manual investigation rather than blind resend. Reconciliation scans at most 2000 authored issues. Tokens require explicit native setup; fine-grained tokens for non-owner public contributions have GitHub limitations. Native Keychain prompts and installed two-Mac connection setup need live acceptance. Owner categorization workflow activates only after merge to main.

### GR14 — Reporting must be reachable in the menu bar

**Susceptible boundary:** Backend/syntax tests pass while the primary menu-bar UI omits reporting controls.

**Cause / solution:** The main app had reporting controls and the menu only had connection setup. Both shipped pages now load the same report controller and styles, with reporting controls in settings.

**Required behavior:** Bug and feature entry points, separate drafts, exact previews and explicit sends work on both surfaces. An absent or duplicate controller element fails the regression.

**Diagnostic trail:** `report_delivery`. Compose and preview remain local; no event is proof of an actual GitHub acceptance.

**Regression tests:**

- `test_report_entry.ReportEntryTests.test_both_surfaces_support_report_compose_preview_and_explicit_send`

**Remaining exposure:** The automated DOM/API harness does not prove native WebKit layout, modal focus, token onboarding or live GitHub behavior. Verify the installed menu with computer use.

### GR15 — Workspace selection preserves identity and copy scope

**Susceptible boundary:** A new source mode changes existing IDs, aliases duplicate a source, missing folders publish empty replacements, or configuration changes race backup source selection.

**Cause / solution:** Persist a canonical source registry with inactive identity records, retain legacy IDs and validate overlaps/protected locations. Saves require a matching revision and idle scan/backup locks. Take the backup source snapshot under that same lock. Check an approved directory's canonical location before scanning/copying it.

**Required behavior:** Migration preserves backups, saved JSON, schedules and per-repo settings. Same-named folders remain distinct. Removal stops monitoring without deleting sources/current archives. Unavailable/retargeted sources fail safely, and saved manual selections no longer depend on the obsolete home setting. Invalid/stale/busy/failed saves retain the old selection.

**Diagnostic trail:** `workspace_configuration`, `repo_checked`, `repo_backup_failed`, `repo_backup_finished`, `status_repo`, `ui_presented`. Successful configuration events contain only mode/result/count; subsequent repo/run/archive aliases explain copy outcomes. Exporting source paths/names is forbidden.

**Controlled counterexample:** The new interleaving regression was run against the parent implementation's backup method and failed because configuration saving was allowed between taking the old source list and acquiring the backup lock. The fixed implementation rejects that concurrent save. The duplicate-name diagnostic regression also fails against the earlier name-based projection: both same-named rows are falsely marked as copying. Backup activity, errors, UI status and problem episodes now use workspace IDs, with legacy-name fallback only when the ID field is absent. The shared JavaScript policy checks that the other same-named card stays ready and receives no unrelated error. These are synthetic findings, not evidence of personal backup incidents. Private reproduction logs remain outside Git.

**Regression tests:** All 16 `test_workspace_registry.WorkspaceTests` methods are required by [golden-rules.json](golden-rules.json), including migration/persistence, alias/collision handling, source availability, revision/lock/write failures, the controlled interleaving, API authorization and sanitized configuration diagnostics. The macOS gate separately runs the native bridge executable's manual-path approval/rejection checks.

**Remaining exposure:** Native URL checks do not prove actual Finder/picker interaction. Separate-volume remounts, inaccessible-volume recovery, concurrent filesystem replacement and source relocation still need live coverage. Destination migration, naming and setup UI remain separate work. See [the configuration contract](../WORKSPACE_CONFIGURATION.md).

## Reporting access incident — 2026-10-09

The MacBook Pro authenticated the saved token as the tracker owner, while a submission receipt recorded `failed / github_access_denied`. GitHub token settings showed no selected repositories or repository permissions. The generic UI error did not explain that sign-in and permission to create an issue are separate checks. The user later confirmed successful delivery to [issue #3](https://github.com/yogoldy/RepoHub/issues/3), corroborated by the local `sent` receipt and GitHub issue lookup. The intervening permission save was not directly observed; do not claim a captured end-to-end permission-change trace.

The UI now identifies access denial and directs the owner to check token validity, selected RepoHub access and Issues read/write; it does not claim that a 401/403 proves missing permissions. Draft bytes and preview identity survive rejection and explicit retry. Operational diagnostics export only the existing enumerated denial code and aliased report identity. No credential or provider error prose is exported.

GR13 additionally requires `test_report_delivery.ReportDeliveryTests.test_sign_in_success_does_not_grant_post_permission_and_retry_keeps_draft`. GR14's existing both-surface controller regression now exercises a successful account check followed by denied submission, actionable feedback, a connection check that does not resend, and explicit retry of the same preview. Native rendering of this new wording and Air onboarding remain pending; automated controller tests do not replace those checks.

## Source-picker and review boundary (GR16)

A repo-home child may appear between review and save, or a late/cancelled native picker callback may belong to an obsolete draft. The native bridge accepts only fixed directory-picker actions with a typed correlation ID on the exact main menu frame. Draft cancellation invalidates that ID. The backend preview validates paths without saving; a reviewed save rechecks both registry revision and the entire candidate fingerprint under the configuration/backup lock. Conflict preserves the approved configuration and asks for a fresh review. `workspace_review` logs bounded outcomes/mode/count, never raw folder paths. Live native focus, cancellation, multi-selection and visible exact-path review require acceptance alongside automated tests.

Native acceptance also found an inaccessible second top-level modal: visually rendered controls were absent from WebKit accessibility. Reuse the existing settings dialog for the setup form; require live accessibility and picker checks, not screenshots or diagnostics alone. See [Pro source-picker acceptance](../PRO_SOURCE_PICKER_TEST.md). Rejected configuration saves produce a bounded failed event without path/prose.

## Client startup freshness — GR06

The menu changed cached backend health when local requests failed or a 20-second timer expired. It then reported stale icons against a fresh original observation. Both HTML surfaces now retain the original snapshot and render a separate client freshness projection. Typed request-failed, timeout and cache-expired contexts explain conservative stale displays; false green still raises disagreement. Native startup/timeout/recovery acceptance remains pending the reliability run.

## Access denial and unavailable storage — GR17

Actual mode-bit restrictions exercise denied root and nested-file reads, denied archive writes and revocation between archive creation and validation. Existing verified bytes/index remain unchanged; accessible independent repos continue and restore of access recovers. Typed errno-based outcomes do not diagnose TCC. Real privacy prompting remains native acceptance work.

## Source substitution — GR18

Canonical path and workspace ID alone cannot distinguish a replacement folder/volume. Add directory file ID and volume UUID when accessible; retain existing IDs. Recheck before reads and publication, block mismatches and require an explicit reviewed selection. Remount testing uses a disposable disk image; physical hot-unplug is not simulated proof.

Live Pro disk-image acceptance passed: unmount retained the prior archive/index, a replacement directory at the former mount path was rejected, and remount of the original HFS+ image recovered with the same volume/directory identity and reused the verified archive. Private receipts are outside Git. This is real separate-volume evidence; physical unplug and privacy prompting remain separate.

## Permission readiness — GR19

Settings shows helper-probed source/destination access, actual notification authorization and installation-matched login registration. An explicit Check access action probes all selected regular files without following links and creates/removes only its own destination test file; it does not verify archives or uploads. Notification requests are contextual, not automatic at every launch. An asynchronous check keeps large trees from timing out the settings request. Native TCC/notification acceptance uses a separate identity; daily permissions are never reset.

Volume checking initially used repeated diskutil subprocesses, making the full regression run unacceptably slow. The helper now reads Apple's persistent volume UUID directly with Core Foundation using a fresh URL for each check, retaining remount/substitution protection without process startup. The slow gate was deliberately interrupted and is not accepted as a pass.

Freshness delivery retains at most one unavailable frame in memory and retries it after reconnect before the current frame. Expired backend observations remain unobserved gaps. Server event timestamps are receipt times, including deferred delivery; they are not proof of the moment pixels changed. Both request timeouts and cache expiry have explicit typed contexts.

### Native picker pathname aliases (reliability acceptance)

The simultaneous-folder picker returned `/tmp/...` for a previously stored
`/private/tmp/...` folder. The draft deduplicated strings, so both appeared before
review despite referring to the same directory. Native picker results now use
POSIX realpath, matching helper canonicalization. Finder resolution uses the same
comparison for approved registry paths. Native bridge checks cover both aliases
and a directory symlink; the real multi-selection repeat remains required.

### Notification request is separate from permission

The isolated native readiness screen remained `notDetermined` after an explicit
request. No grant/refusal prompt was successfully observed, so this is not evidence
of a macOS permission decision. Calling a request must not continue to display
“not requested”: the native app now records pending/completed/failed request states
without exception prose and suppresses duplicate requests while one is pending.
Only the OS authorization state can say allowed or denied. Readiness JavaScript
regressions cover those combinations; native grant/refusal acceptance stays open.

The bounded offline-frame slot is also compare-and-clear: completion of an older
POST cannot erase a newer freshness frame queued while that request was in flight.
A JavaScript concurrency counterexample is required by the gate's delivery suite.

## Two-Mac staging interruption and payload drift (2026-10-10)

Acceptance must not depend on the lifetime of the controlling tool session. A detached watchdog starts before any pause, and durable restore intents precede launchd bootout; locked cleanup resumes/stops only owned test labels and restores daily registrations even on a protected-state mismatch. Payload transfer is verified against a manifest from the exact clean Pro Golden Gate build, not an independent Air compilation. Controlled guard/cleanup/controller-loss regressions are in `test_reliability_acceptance`; actual native interruption and both-host permission evidence remain open. See [two-Mac protocol](../RELIABILITY_TWO_MAC_ACCEPTANCE.md) and GR12.

## Native picker obscured by the menu (2026-10-10)

The first Air acceptance at be02a30 showed the NSOpenPanel behind the floating menu popover. Helper/API operation and draft-only removals were intact; the private saved registry still matched its initial API snapshot. This is a native window-order failure rather than a backup failure. Close the popover before showing the independent picker and reopen its retained WebKit draft on choose/cancel. The two-host matrix case 02 now explicitly checks unobscured controls and retained drafts. Air cleanup restored its existing launch jobs and matched all protected-file hashes. Native acceptance of the fix remains open; compilation is not proof of window order.

## Temporary staging app is not notification permission evidence (2026-10-10)

Air's notification daemon rejected the random temporary-path identity before a
permission decision. An existing development signature alone did not fix it.
Registration of an owned Applications copy allowed the real notification state;
the unchanged ad-hoc candidate also observed grant/revocation there. This is a
staging registration fault, not evidence that a user refused notifications.
The harness now records exact installed assets, refuses existing/redirected paths,
and unregisters/removes only its matching copy. Changed assets remain for review;
watchdog restoration of daily jobs still proceeds. GR12 includes preservation
counterexamples. Air grant/revocation, restart and synthetic backup after denial
have private evidence, but clean initial-refusal and both-host repeats remain open.

Actual source privacy must be tested through the background helper. Its system
Python identity is shared with daily work; resetting or revoking that identity's
permissions in the daily account violates isolation. Case 07 therefore requires a
separate test account. POSIX denial is still distinct from an actual TCC decision.


## Cross-account acceptance must not impersonate the daily installation

A standard permission-test account owns neither the daily launch registrations nor
its private configuration. The same-user staging command therefore cannot safely
be used under that account. `reliability_account_guard.py` gives each account its
own journal and detached watchdog, with a shared read-only flock serializing test
startup and daily restoration. An active test lease prevents restoration even
before its helper starts listening. Cleanup releases that lease only after the
exact owned test jobs are gone; an unknown helper on the fixed native port blocks
the daily client from restarting against test data. The daily account captures
its own protected files and rollback, without exposing them to the test account.

Seven required GR12 counterexamples cover ownership/redirects, bounded single-use
leases, unknown-port rejection, active-before-listen restoration exclusion,
restoration despite a disclosed baseline change, incomplete test cleanup and
watchdog retry. Actual cross-account interruption and the native permission matrix
remain live acceptance; regression simulations are not those results.


### launchd shutdown acknowledgement precedes port release

The first real isolated-account hold at 5ec10cf booted out the known daily jobs,
but its immediate bind check still found the helper port occupied. No test jobs
started. The detached daily watchdog retried after the exiting helper released
the port and restored both registrations with matching protected hashes. The hold
now waits up to five seconds for port release while retaining the coordination
lock; timeout still fails closed. Two counterexamples cover delayed release and
an occupied port that never clears. No process is killed based on the port alone.


### Fixed-port handoff must be checked by the receiving account

The next real hold passed the daily account's bind check but test admission failed.
A controlled port-only repeat found no listener, yet the test UID received errno 48
(address in use) while the daily UID could bind. netstat recorded old 8767 connections
in TIME_WAIT. The test UID became able to bind after 15.1 seconds of observation;
no test helper was launched during the probe. Guarded restoration again preserved
all protected files and restored both daily labels.

Test admission now waits up to 45 seconds as the receiving UID, under the same
coordination lock, then rechecks expiry. It records each ownership/candidate/lease/
port check privately in admission.json. Wrong identity or stale hold fails before
waiting or launching. The guard never changes kernel TCP settings or starts the
daily client against an unknown helper. Cross-account TIME_WAIT behavior is an
observed staging constraint here, not an application backup or privacy failure.


## Remote login is not actual permission acceptance (2026-10-10)

The isolated Air test account had working native control and SSH, yet its actual
background helper rejected a synthetic Desktop source with EPERM while the SSH
caller could read it. A native Terminal re-bootstrap of the same owned launch job
reproduced the denial. Source review failed without changing the saved registry.
No helper-specific folder-access prompt/entry was observed. Session evidence
showed the Test account logged in but not on the physical console. That is a
variable to eliminate, not a diagnosis that console activation will necessarily
fix the helper's privacy attribution.

Keep caller/picker/background-helper access evidence separate. EPERM alone does
not prove a user explicitly refused TCC; a successful picker does not grant the
helper equivalent access. Actual prompt refusal/restoration remains a release
blocker until reproduced with the correct isolated session/identity. Do not reset
daily TCC, grant broad access or mark the case passed to make progress appear
complete. Stop and restore daily services before requesting user-assisted login.
GR17/GR19 regressions establish fail-closed read handling and optional notification
behavior, but do not replace this native evidence.

The same staging identity showed real notification grant/revocation and restart
with successful backup after revocation. Its initial request reported failed,
not a proved explicit refusal. Record request lifecycle and observed authorization
separately; do not infer a user decision from the banner or disabled switch.


Apple's [responsible-code guidance](https://developer.apple.com/forums/thread/678819)
provides a concrete next attribution hypothesis: the system-Python helper launch
agents currently have no `AssociatedBundleIdentifiers`. Inspecting that omission
is not proof that adding it fixes the missing prompt. Preserve the failing helper
observation, distinguish GUI session membership from physical-console ownership,
and require an actual isolated helper refusal/restoration test after any change.
A packaging change starts a new candidate and both-host acceptance again.


## Background Python shim lost app attribution — GR19

Air private probe reference 7c57f4c7eb3446c1afb6104898bcc6e2 isolated the missing
Desktop prompt. Local console activation did not resolve the original helper
EPERM. Adding AssociatedBundleIdentifiers alone did not resolve it; neither did
launching the same Python version directly. Narrowly filtered system logs
attributed access to Apple's Python/tool shim, rather than RepoHub. The denied
review left the saved registry unchanged. EPERM still must not be described as a
user refusal without actual OS evidence.

A Pro-built, uniquely owned native launcher entered the unchanged Python helper
via execv. The actual macOS Desktop prompt appeared for that probe identity.
Clicking Don't Allow blocked the helper's review; restoring only that test
identity's Desktop switch through System Settings recovered the same review.
The user authenticated that restoration directly. No daily TCC reset or Full
Disk Access was used. This closes a controlled attribution experiment, not the
complete release matrix or an accepted candidate.

The fix enters helper mode through the app's native executable before any menu
initialization, retaining the interpreter, config, environment and launchd PID.
execv avoids a supervisor orphaning Python when its job stops. The production
installer and both guarded staging paths use the same command builder. The gate
checks strict arguments, inherited environment, exit/failure propagation and
same-PID SIGTERM ownership. Detached watchdogs include the builder dependency.
These checks prevent lifecycle/packaging regressions; only actual native reads
can prove TCC permission behavior. A new candidate must repeat the full matrix
on both Macs, including refusal/restoration/restart.


## Status wording must not become backup evidence — October 16, 2026

Presentation grouping can accidentally promote a Finder-only exception, a stale
frame or a different archive's upload into success. Keep the existing internal
policy intact; independently validate the new category and sentence against the
original observation. GR06 and GR09 require cross-language mapping/counterexample
and export-privacy regressions. Unknown evidence stays unknown. Native pixel,
wrapping and installed-menu checks remain separate from diagnostic agreement.


## Information guide title overlaps scrolling text — October 16, 2026

A sticky heading inside a padded scrolling dialog left an exposed strip above
it. Separating the full-width header from the guide scroll container removes
that overlap. Keyboard focus can also scroll an overflow-hidden ancestor when
descendant content contributes to its scroll area: layout/paint containment on
the guide body prevents that second failure. Browser keyboard-to-bottom evidence
kept the outer dialog at scroll zero. Native WebKit scrolling, narrow-window
wrapping and keyboard/Escape remain release acceptance checks; this browser
result does not close that backlog.


## Timing evidence must agree without destroying observation identity

Secondary location/due/date/countdown claims now have independent selected-repo
receipts. Private date strings are compared against the original observation;
only fixed codes and bounded whole minutes enter logs/exports. Unknown types,
missing selected receipts and arbitrary dates fail closed. GR06/GR07/GR09 name
the new regressions. Existing CI test discovery needs no YAML modification.

A first implementation included each poll's observed_at in snapshot identity,
breaking cross-view correlation even when meaningful evidence was unchanged.
Drop that sampling field and bucket remaining time to displayed whole minutes
for identity; retain original snapshots unchanged. Periodic due dates use the
saved wall-clock anchor directly, avoiding floating subtraction drift.
Native countdown readability and actual sleep/power behavior remain unproven.


### Whole-minute countdown boundary

Browser acceptance found a nominal 30-minute wait displaying 31 minutes. Tiny
monotonic/wall-clock floating-point conversion noise rounded upward twice: once
to seconds and again to minutes. Derive remaining seconds from the projected
wall due time and remove sub-millisecond noise before the existing upward
rounding. A deterministic fractional-clock counterexample protects the boundary;
scheduler eligibility itself is unchanged.


## GR20 — coordinated app replacement

An ad-hoc native replacement lost its prior macOS permission requirement and
rolled back, while a browser preview continued serving newer web assets against
an older helper. A working source build did not mean that the installed app had
updated. The new bundle builder pins Python and Sparkle, includes web/helper
resources in one manifest, and checks that the connected helper reports the
same release before loading the menu. Test bundles use a disposable identity,
state and port. Native integrity and complete Sparkle package builds now run
inside the existing macOS gate; the workflow invokes that gate already.

The web-resource boundary now uses an explicit list in `tools/package_app.py`.
A controlled build using the former whole-directory copy included injected
`.env`, Finder metadata, scratch files and a symlink target in its valid resource
manifest. Hashing that manifest did not establish that the files belonged in a
release. The builder now copies only declared regular web files, rejecting a
missing required asset or a linked source file/directory. All 17 existing served
assets remain; this does not remove the dashboard or retained notes route.
The gate rejects a served route omitted from the package list. GR20 registers
the actual-build resource-selection regressions and the omitted-route
counterexample. Compilation/signing are stubbed only for the synthetic selection
tests; the macOS gate separately compiles and builds the complete native bundle.
Private local files are excluded, not deleted. No new runtime diagnostic event
or status rule is required for this build-time boundary.

A SIGTERM to a bundled helper waits for the actual backup lock, covering a
backup that begins after a native idle check. The updater never sends SIGKILL.
Actual signed-upgrade/failure recovery remains acceptance work. Production
signing, notarization and permission continuity are not established by ad-hoc
test signatures. No daily installation or launch registration is changed.


### Loopback startup must not depend on hostname resolution

The first updater CI run timed out starting the synthetic helper. Isolating
scheduler/proxy inputs did not fix it. The retained child stack from the second
run showed `HTTPServer.server_bind` blocked in `socket.getfqdn` under the runner's
Python 3.15. Bind with TCPServer and assign the fixed loopback name/actual port;
no resolver is needed. A deterministic regression makes getfqdn raise, confirms
the standard server counterexample, and requires the RepoHub server to bind.
Wildcard binding is rejected. This is an application change, so prior native
updater acceptance is historical until repeated for the new candidate.


### Permission identity across signed updates (GR20)

The October 22 transition from ad-hoc build 7 to Developer ID build 9 requested
Desktop consent again; Leo selected Allow. The preserved ad-hoc app's designated
requirement was a binary hash with no Team ID. Build 9 instead has the persistent
Developer ID requirement for Team `LJM5FKB7DY`. This is evidence of a signing-identity
transition, not a reproduced signed-to-signed permission failure.

`tools/signing_identity.py` records the observed app, Python helper and cloud tool
identifiers/requirements from build 9. Both Developer ID packaging and archive
preparation reject another team, changed helper identity, custom/hash-only
requirements and escaping component links. Counterexamples include a valid
signature with an incompatible declared requirement; notarization is insufficient
for this contract. The installed build 9 passes this read-only check. No daily
privacy setting is reset or edited. A subsequent signed Sparkle update must still
demonstrate retained consent and helper-observed source access independently.

Apple documents designated requirements and privacy-resource sharing in
[TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements).


## GR21 — accepted source and atomic release availability

A passing feature-branch or PR gate is not an accepted main release. Publication
requires the successful main-push workflow and job for the checked-out exact SHA;
a new main commit during upload prevents that draft from publishing. Tests inject
upload failure, altered downloaded assets and superseding source, and require no
publication or package deletion. Latest-release uncertainty or a bad historical
receipt prevents all cleanup. Cleanup retains current plus three prior managed
packages and preserves tags and unrelated releases. The workflow is syntax-checked
by pinned actionlint inside the macOS Golden Gate. Real Apple service/GitHub
publication remains open until credentials and the first production release.

### GitHub drafts do not yet create their Git tag

The first local publishing gate passed, but a real disposable GitHub draft probe
showed the draft's exact target was present while no tag existed. An immediate
`commits/<tag>` verification would therefore stop every first publication. Check
for conflicting existing tags before creating the draft; validate the draft's
exact target SHA, and resolve the tag after publication. The regression includes
a missing-tag normal case, foreign tag collision and moving-branch draft target.
The actual text-fixture upload/download matched and its draft/assets were removed.
No production update was published.

### Explicit personal delivery before Apple signing

Apple distribution readiness was incorrectly made a dependency of personal
Sparkle delivery. An explicit personal_adhoc mode preserves HTTPS, bundle identity,
archive authentication, exact-main acceptance and retention guards while omitting
Apple submission. Conflicting app/manifest distribution flags are rejected.
Background discovery uses Sparkle's actual SUScheduledCheckInterval key and
one-hour minimum; the native settings check reads the built bundle through
SPUUpdaterSettings. Silent installation remains disabled. Developer ID mode keeps
its original certificate/notary requirements.

### Legacy Homebrew interpreter responsibility identity

The Pro’s read-only migration preflight found that the configured Homebrew bin
interpreter executes the framework’s Python.app binary. Comparing only the bin
symlink’s target falsely rejected the legitimate service before any stop. Resolve
the real process path by probing exactly the configured interpreter in isolated
mode, then retain the same strict libproc PID-path comparison. The regression
requires the configured interpreter and rejects malformed probe paths; no name-only
process matching or generic Python termination is introduced.

### Register a replaced bundle before loading its login agent

Two real Pro migrations failed with launchctl bootstrap EIO (5) and automatically
restored the old app/helper with matching protected hashes and 13 repos. The same
published executable loaded its argument guard normally and both disposable
launchd tests passed, so an executable-loading fault was not established. Refreshing
the replacement bundle through Apple’s lsregister before bootstrapping the unchanged
frontend plist succeeded: matching packaged build 1, 13 repos, preserved configuration.
The regression fixes this ordering and retains future bootstrap stderr only in the
private migration journal. This demonstrates the working ordering on this Pro; it
does not establish launchd’s undocumented internal reason for the earlier EIO.

### Settings navigation must not silently consume an unsaved draft

Opening another page, native permission-readiness entry, Close and Escape are not
save actions. Keep a canonical draft baseline, ask before discarding actual edits,
and serialize the existing token/revision-checked save. Failed requests preserve
editable values and do not claim confirmed persistence. Native access entry must
honor a declined discard decision before fetching/replacing the schedule form.

The folder controller is shared with the full status page: test both hosts. Review
must not save; busy saves block duplicate submits and navigation; conflicts keep
the selected draft and offer explicit reload. Only a successful reviewed save
returns to Settings home. GR22 registers the actual controller regressions. Native
picker, privacy prompts and installed WebKit behavior are separate acceptance cases.

### Moving technical details must preserve repository identity

A technical disclosure outside the summary still belongs to the selected repo.
Include that identity in its markup, keep open/closed state per repo, and ignore
queued toggle events from detached nodes. Otherwise identical technical text can
reuse another repo's disclosure state. The isolated information-controller
regression exercises switching, late toggles, refresh and an empty selection;
GR06 registers it. Browser checks also cover the fixed About header, Back,
Escape and the existing Show me action. Installed WebKit validation is pending.

### Finder view settings may share the Backed up display — October 17, 2026

Leo approved the normal Backed up card, green check and headline for the existing
ordinary .DS_Store-only exception. This supersedes the earlier information-icon
requirement for this presentation only. The raw comparison stays different, the
legacy internal view stays background/not-ready, and backup eligibility, archive
verification and retention remain unchanged. Policy status-clarity-5 describes the
new display; versions 1–4 keep their original diagnostic interpretation.

Diagnostics independently require fresh source verification, the same verified
archive, no pending backup/failure/active creation, and upload acknowledgement for
that archive. They retain finder_only_project_match instead of claiming exact
current byte equality. Technical details disclose the .DS_Store difference. GR06
registers positive, conservative, legacy-version and real temporary-backup/export
regressions. Native pixels and installed-app acceptance remain pending.

## A correct expanded time does not prove a compact card displayed it — October 17, 2026

The collapsed card overview adds a second timing location. Policies 4 and 5
check only the selected expanded receipt, so they cannot establish that every
card showed its time. Policy 6 requires each card's scheduler receipt and a
small DOM observation of its compact meaning, date attribute and actual text.
The horizontal overview always supplies all card receipts. When a repo is
selected it adds exactly one expanded-line observation; a collapsed overview
uses a null selection. Only the actively selected repo has technical details.
The scrolling-grid prototype is preserved in local commit 792e925. The presentation is computed once
per repo per render and shared by both locations. Diagnostic expectations remain
independent of the renderer. Missing, hidden or incorrect card lines are tested
without using the expanded line as their evidence. Earlier policies retain their
original contracts.

Only the fixed card/detail surface code and existing bounded timing facts enter
logs and shareable exports; exact dates remain in the private comparison request.
GR06 and GR09 register the regressions. Existing Python discovery runs them in
GitHub Actions without a YAML change. Browser layout and native WebKit acceptance
remain separate from these DOM-observation and evidence-contract tests.

## First-run setup, destinations and discovery — October 18, 2026

GR23 requires a fresh package to start without a personal configuration and remain
idle until an exact reviewed draft passes helper-owned access checks. Setup saves
share the backup/scan/configuration locks and journal their directory moves and
metadata writes. A prepared journal blocks operation until recovery succeeds;
revision, identity and archive checks do not become optional during recovery.
Native checks compile the app, exercise a unique test bootstrap and restrict the
welcome bridge to its exact trusted web view/page/port. UI controller and HTTP
tests distinguish review from save and explicit first-backup requests.

Installed acceptance exposed a native-only draft reload failure: an unhosted
JavaScript confirm silently refused the action. The real controller regression
models that refusal, proves reload restores saved selections without calling
apply, and checks that discovery/access/completion UI cannot leak from the old
draft. Reload is an explicit draft discard and uses no browser dialog; it waits
for native picking or discovery to finish.

GR24 keeps stable IDs in metadata and names backup folders after sources, grouping
duplicate leaf names by their distinguishing parent paths. Existing paths change
only on reviewed apply. Hashes guard migration; uploaded observations cannot be
reused after a path changes. Switching destinations leaves old archives in place
and requires a new copy. A missing or replaced destination is never recreated or
silently rebound. General provider support is outside this release.

Actual Finder acceptance also found the native Repository Backups action still
hard-coded to the legacy collection. It now resolves only the helper's fresh
selected root, with configured/canonical/existing-directory checks and no default
fallback. The macOS bridge regression covers changing the selected root,
unconfigured or malformed status, redirected/file/missing targets and no path
creation. Its trusted page action still accepts no path or URL from JavaScript.

GR25 makes recursive Git discovery a bounded, cancellable candidate scan. It does
not save selections or run backups. Git markers are validated, Git internal and
protected folders are excluded, and unsupported external history is disclosed.
Ordinary folders and repo-home mode keep their existing behavior. Source paths,
names and review fingerprints stay out of the typed setup/discovery diagnostics.

The first follow-up branch run exposed a cancellation race after the last
traversal check: an accepted request could publish complete instead of cancelled.
The regression now pauses the worker at its final identity check with events,
accepts cancellation, then releases completion. It fails reliably before the
fix. Final publication checks cancellation under the same lock, retaining
incomplete results and a partial diagnostic rather than claiming a full scan.

See [first-run acceptance](../FIRST_RUN_SETUP.md) for current evidence and the
remaining native permission, iCloud and installed-update checks. The macOS PR,
main and publication workflows all execute the same complete Golden Gate; new
Python/JS wrappers are discovered automatically, with registered test IDs failing
the gate if absent, skipped or unsuccessful.

## GR26 — Staged updates preserve Stable and package identity

### Repeatable local Dev credentials

The first signed Dev handoff deliberately discarded its hidden inputs, but it
was incorrectly described as a finished one-time workflow. A failed draft lookup
also consumed the one-use launcher and required a replacement script. This was
developer publishing friction, not a requirement for normal update recipients.

`tools/local_dev.py` now separates one-time secure setup from repeatable explicit
Dev publication. Setup checks the original public key against repository
configuration, verifies private/public continuity and Apple credentials, and
saves the existing material in Keychain only after success. The Developer-ID-
signed helper trusts its own code identity; no allow-all ACL or silent credential
replacement is used. Bounded pipe input is read completely rather than assuming
one read returns the entire credential bundle. No signer is shipped to app users.

The gate runs without signing credentials; source drift or a failed gate prevents
loading them. Missing/locked/cancelled Keychain access and an untrusted helper
stop before release mutation. A failure records its actual stage and permits a
new run of the same command. Child signing output is not persisted or echoed;
errors expose typed reasons only. These developer run records are private, not
backup readiness evidence or shareable application diagnostics.

Fixtures exercise two publications without secret prompts, gate/source failure,
locked access, publisher failure/retry, existing-item refusal, configured-key
mismatch, secret-free errors, unsigned-helper refusal and a disposable Keychain
roundtrip without changing the user's search list. Fixture UI is explicitly
disabled so a locked-item test cannot wait for a consent dialog. Real Keychain
provisioning still needs the owner's secure entry; a subsequent signed Sparkle
update and retained Desktop permission remain separate acceptance work.


A single GitHub latest feed made every accepted main release visible to every
installation. The staged-channel contract separates local Dev, full-gate Testing
and explicitly promoted Stable. Stable remains the default on each Mac. Native
actions accept only fixed channel names and exact owned menu-page requests;
revision conflicts and an active update/backup prevent an ambiguous save.

A saved Dev preference previously worked without a separate deliberate opt-in,
and every installation showed experimental choices. An explicit Boolean local
preference now enables those choices only after restarting the app. Missing,
false or malformed enablement forces effective Stable selection even when a Dev
preference remains on disk. Native saves reject experimental channels without
that opt-in; page messages cannot enable it. The launch-time policy snapshot
prevents an external preference change from switching policy midway through an
update session. Tests use disposable preference domains and a second process to
check persistence and revocation without touching either daily installation.
The shipped controller hides choices until a valid native response enables them;
forged DOM selection or contradictory replies cannot enable saving. The page
must not imply confirmed Stable settings when loading failed: it shows
settings as unavailable and disables its update action until a valid reply loads.
Diagnostics preserve the effective channel and a bounded enabled/disabled policy, rejecting
contradictory disabled/experimental combinations independently of the UI.
The read-only browser check also reproduced shared flex-row styling overriding
the action container's `hidden` attribute. Scoped hidden selectors now force
both experimental containers to `display: none`; the October 21 browser readback
confirmed this computed style and the absence of channel Save/Cancel controls.
That preview has no native bridge and does not count as installed channel acceptance.

Counterexamples cover wrong channels, missing/skipped/stale checks, corrupt
archives, uploaded-byte mismatches, foreign/failing GitHub runs, incomplete
Pro/Air acceptance, missing Stable approval and a substituted publisher lock.
Promotion changes feed/proof metadata while preserving the signed archive. A
public-key RFC fixture passes cryptographic verification; altered bytes with a
matching rewritten checksum still fail signature verification. Interrupted
promotion can be explicitly resumed only after its requirements are checked
again. Candidate/prerelease feed publication must not move public latest.

The first local signed Dev attempt on October 22 passed its 76-test focused
gate and credential preflight, then stopped after creating draft build 8. GitHub's
release-by-tag REST endpoint returned 404 for that unpublished draft; the
draft-aware `gh release view` returned the expected metadata. Candidate creation
now uses the draft-aware lookup and checks the exact tag, source, draft and
prerelease flags. The regression first reproduces the 404, then rejects foreign
targets/tags, published releases, missing prerelease flags and reserved tags.
Build 8 remains reserved and unpublished, with no assets; the next attempt must
use a higher build and fresh clean-source gate. This failure did not build or
install a package, change a channel feed, or move Stable.

Shareable diagnostics add bounded update_channel and experimental_channels enums and typed reasons;
an update ready state is not repository readiness or confirmed cloud upload.
Live channel publication, Apple services and installed channel/permission
continuity remain separate acceptance evidence, not implied by these fixtures.

The optional manual `validate_signing` workflow input exercises real Apple
credentials only after the complete clean-source gate. Counterexamples reject
push/PR/fork invocation, stale or skipped gate evidence, a changed source digest,
corrupt artifacts and failed independent archive signatures. Validation packages
use a deliberately non-promotable receipt. The workflow has read-only repository
permissions, never publishes or installs, and records bounded failure evidence
while cleaning temporary packages and signing material. Apple service acceptance
still requires an actual successful run; these counterexamples do not imply it.
