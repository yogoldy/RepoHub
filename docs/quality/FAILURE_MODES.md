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

**Required behavior:** Reject unstable snapshots; preserve old backups; detect same-size/same-mtime edits.

**Diagnostic trail:** `repo_checked`, `archive_stage`, `repo_backup_failed`. Join repo/run/archive/observation aliases; event presence alone is not proof of a successful outcome.

**Regression tests:**

- `test_hub.HubTests.test_same_size_same_mtime_edit_is_detected_and_replaced`
- `test_hub.HubTests.test_timestamp_only_changes_match_hashes_and_do_not_replace_backup`
- `test_hub.HubTests.test_metadata_preserving_change_during_snapshot_is_rejected`
- `test_hub.HubTests.test_change_during_backup_does_not_publish`

**Remaining exposure:** Concurrent writes can force retries. No filesystem snapshot or transactional database capture is provided.

**Hosted-test lesson:** CI exposed Git background maintenance removing `objects/maintenance.lock` between inventory and hashing in a restore fixture. The fixture now disables automatic maintenance/GC before committing. Production concurrent-write rejection remains intact; an idle synthetic fixture must not silently depend on the runner’s Git defaults.

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

**Susceptible boundary:** Green check uses old archive data, stale hashes, missing upload flags or an unavailable helper.

**Cause / solution:** Use the shared status policy and join archive/observation/run identities; revoke stale/failed receipts.

**Required behavior:** Green requires fresh matched hashes plus exact-archive uploaded acknowledgement; absent view receipts do not prove agreement.

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

