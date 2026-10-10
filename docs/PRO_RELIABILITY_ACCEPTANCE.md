# Reliability acceptance checkpoint — 2026-10-10

## Release state

Implementation is on `codex/workspace-setup`; the five-goal acceptance pass is
**not complete**. Main is not promoted. The Pro keeps its previously accepted
`5e24009` application; the Air is unchanged. New destination selection, provider
integration and broader onboarding remain outside this pass.

At implementation commit `53ef1d5`, the clean macOS Golden Gate passed **180 Python
tests, zero skips**, JavaScript syntax/status/delivery/draft/readiness suites,
native/cloud builds, 70 native bridge checks and 20 notification-readiness/problem
checks. The receipt confirms unchanged clean source. A final clean gate on the
checkpoint commit and GitHub's exact-head check are additionally required; private
receipts/logs are retained outside Git. An automated pass is not native acceptance.

## Goals and evidence

| Goal | Implemented and verified | Required evidence still open |
| --- | --- | --- |
| 1. Startup freshness | Original backend observations are immutable. Typed current/request-failure/timeout/cache-expiry context controls an independent display projection. Regressions detect false green icons, preserve privacy, and replay one bounded offline frame after reconnect without dropping a newer concurrent frame. | Installed native delayed-start, request failure, timeout, cache-expiry and recovery correlation on this candidate. |
| 2. Simultaneous folder selection | Three native panel rows were simultaneously selected. Two links resolved to one source and the other to a same-named source elsewhere. This exposed a `/tmp` versus `/private/tmp` duplicate in the draft. POSIX realpath now matches helper canonicalization; Swift checks prove alias collapse and approved Finder resolution. Existing review/revision/removal preservation regressions pass. | Repeat corrected native multi-select, cancellation, draft removal, review/save, backup and restart; do not count the failing pre-fix draft as a pass. |
| 3. Denied/revoked access | Seven controlled tests include real mode restrictions on root/nested files/destination, revocation during source verification and destination publication, independent accessible-repo success, preservation of the prior archive/index, and recovery. Errno is classified separately from missing storage and generic I/O; it does not establish TCC denial. | Installed menu blocked-operation/retry/recovery evidence, plus an actual isolated macOS privacy refusal/restoration case. |
| 4. Unavailable/replaced volumes | Real disposable HFS+ disk-image unmount, replacement directory at the former mount point, and original remount passed. Previous archive/index stayed unchanged; replacement was rejected; original volume/file identity recovered and the same archive was reused. Four mandatory identity regressions cover migration, explicit replacement review and unchanged IDs. | Physical hot-unplug is deliberately outside this pass. Sustained replacement races, unusual filesystems and cloned identities are not claimed covered. |
| 5. First-launch readiness | Fresh native Settings opened automatically. Native Check access showed helper-observed source/destination access and correctly withheld login confirmation for the isolated installation. The helper probes regular files without following links and uses only its own temporary destination file. Notifications are optional/contextual. Request progress/failure and interrupted-request recovery have separate typed UI/Swift regressions. | Actual isolated notification grant/refusal/revocation/restart and macOS source privacy acceptance. The observed `notDetermined` state is not proof of a prompt or decision. First-launch layout/clickability must be repeated on the final candidate. |

## Diagnostic and safety findings

- The initial slow gate used repeated diskutil subprocesses. It was interrupted,
  not passed. Direct Core Foundation volume UUID reads remove that overhead while
  retaining persistent identity and fresh URL lookup on every check.
- The private gate's restrictive umask exposed a test fixture restoring a file to
  0644 instead of its original 0600. Fixtures now restore captured permissions;
  the failed receipt remains a failed test run, not an app-corruption finding.
- A native multi-selection draft revealed pathname aliases before any save.
  Native bridge canonicalization and its regression were committed separately.
- A notification request left OS authorization undetermined. Request state is now
  distinguished from permission; no permission is invented from the attempt.
- Computer use connected successfully for the initial readiness/picker actions,
  but fresh-app lookup also timed out twice, including the corrected repeat.
  Those attempts cannot close native acceptance. They are tool failures, not
  proof that the application hung.
- Each isolated run had a timeout guardian and unconditional restoration. The
  cleanup receipts confirm preserved config/default schedules/per-repo schedules,
  native/runtime hashes and restored daily jobs. The harness initially named the
  wrong registry file in its hash list; that entry was absent and proves nothing
  about registry-byte preservation. No test selection was saved into daily state.
  Correct the harness to hash `data/workspace-registry.json` before the next run.
- The tool later relaunched a test app after its guardian finished. Only that
  identified test-owned process was terminated. Daily native/helper processes
  remained running. The final read-only probe showed 13 daily sources,
  diagnostics recording and the unchanged installed native binary hash.
- Private test destinations disabled provider observations. No iCloud-upload,
  independent cloud restore, credential migration or new permission grant is
  claimed. Daily permissions were not reset and Full Disk Access was not sought.

## Reproduction and next acceptance run

Use small synthetic Git repos with ignored content and an empty directory, two
same-named source folders, manual-only settings, a unique test app identity and
an isolated helper/state/destination. Stop all daily UI/helper clients before
reusing the native fixed port; protect the actual registry and configuration
files and arrange a guardian that restores the jobs even if computer use hangs.

1. Reconnect computer use to the unique app; reject stray clients in diagnostic
   evidence. Record first-launch readiness pixels and actual helper probes.
2. Select multiple native rows in one panel, including duplicate aliases and
   same-named distinct sources. Review exact canonical paths, cancel/remove/save,
   create complete backups, restart and verify the saved IDs/settings.
3. Stop/resume only the isolated helper to induce request timeout and cache
   expiry. Compare displayed states with original observations and typed client
   reasons; verify recovery and that falsely green input still disagrees.
4. Revoke/restore synthetic file and destination modes and inspect menu text,
   scoped retries, unchanged old archive hashes and continuing accessible repos.
5. Exercise actual macOS privacy and notification decisions using only a fresh
   test identity/account. Do not reset daily permissions or substitute POSIX
   restrictions/mocked authorization for TCC evidence. Record what the OS actually
   reports and the app's response after restart.
6. For separate-volume repetition, create a new small disposable HFS+ disk image
   under a private temporary directory. Mount it at a test-owned location, build a
   known-content source and verified archive, unmount, place replacement content
   at the former path and expect `changed`, then remove only that replacement and
   remount the original. Confirm unchanged workspace identity/index, matched
   manifest, reused archive and finally detach the owned image. The committed
   source repeat at `7d21621` passed all these assertions.
7. Restore daily jobs and inspect preservation receipts. Once all required live
   evidence exists, run the clean committed gate, require the current GitHub
   check, and deploy to the Pro with rollback and installed-asset verification.
   Then inspect the installed daily menu and correlate diagnostics. Keep the Air
   unchanged. Do not mark this checkpoint as final release approval.

The precise remaining blocker is reliable computer-use access to the isolated
native candidate and its required OS permission cases. No new application version
has been deployed as a workaround for missing evidence.
