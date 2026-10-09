# MacBook Air staging experiment

This is a real two-Mac test of RepoHub's local backup service, native menu-bar HTML,
macOS iCloud observations, and independently received archive restoration. It is
not an exhaustive certification of every UI state, power condition or cloud provider.

## Fixed inputs and isolation

The installed Air app and helper were built from RepoHub commit
`f1e48871355772c3158c64b155bdf1dac9cc8e7f`. The app was compiled on the Air with
Swift 6.2.3, targeting macOS 13; the Air runs macOS 26.3.1 and Python 3.9.6.
Building locally is an explicit experimental variable. Identical-binary testing is
still a separate check. The original source checkout was not edited or updated.

The public fixture is [pypa/sampleproject](https://github.com/pypa/sampleproject),
cloned with full history at `621e4974ca25ce531773def586ba3ed8e736b3fc` (197 commits).
Its code, dependencies and workflows are never executed. A local synthetic commit
exercises history preservation; nothing is pushed upstream. Two separate synthetic
Git repos, Alpha and Beta, are unchanged controls.

The staging service monitors only `~/Library/Application Support/RepoHub-Air-Test/repos`.
Its output is a new `RepoHub Air Test/Snapshots` folder in iCloud Drive, separate from
personal Repository Backups. App state occupies the previously absent standard
`~/Library/Application Support/RepoHub` folder. The native app is in
`~/Applications/Repo Hub.app`. Distinct LaunchAgents are named
`com.leogoldberg.repohub.airtest.service` and `com.leogoldberg.repohub.airtest.app`.
They start at login; the helper keeps running while the Air is awake.

The migration installer was **not run**. Existing Desktop folders, personal repos,
legacy backups and unrelated LaunchAgents were not changed. Only test-owned files
were added, deleted or pruned. Latest-only retention still requires verified bytes
and macOS upload acknowledgement before deleting a preceding test snapshot.

## Test scripts and evidence

- `tools/air_staging_test.py` performs the fixed sequence below against the installed
  loopback service. It refuses different input/output roots and requires an explicit
  fixture marker and upstream commit. It writes stage events, API status snapshots,
  command receipts, assertions, independent source baselines and restore receipts.
  Original default and per-repo settings are restored in `finally`.
- `tools/air_staging_progress.py` adds one deterministic, incompressible 48 MiB file,
  observes the real upload and checks its complete restore. It does not fabricate
  percentages, upload acknowledgements or UI receipts.
- `tools/air_staging_observer.py` polls real staging status once per second for at
  most 15 minutes. It stops when `observer.stop` appears. It never submits rendered
  UI evidence on a view's behalf.
- `diagnostics_report.py` reads the app's own diagnostic logs for retrospective
  review. Preserve raw logs outside Git along with the stage evidence: UTC times,
  observation IDs, helper sessions, run IDs and archive references connect them.

These are guarded scripts for this explicitly provisioned experiment, not a general
installer. Before starting, create `STAGING_TEST_AUTHORIZED.json` under the private
case root containing exactly:

```json
{"repo":"SampleProject","upstream":"https://github.com/pypa/sampleproject.git","commit":"621e4974ca25ce531773def586ba3ed8e736b3fc"}
```

Provision a fresh full clone and idle staging service before replaying. The script
is intentionally not rerunnable on its mutated fixture: it fails its original-HEAD
check after creating the synthetic commit. Preserve previous attempt evidence rather
than overwriting directories or resetting someone else's checkout. Check both exit
status and `result.json`; a bounded timeout is a failure, not an upload success.

## Results on 2026-10-09

The main sequence passed **34 assertions**. Its real two-minute quiet-period test
completed after **134 seconds**, including scheduler polling. Settings were restored.

| Condition | Expected result | Observed result |
| --- | --- | --- |
| Full-history public clone | Initial backup matches and restores | Passed |
| Delete `src/sample` | Detect deletion, replace only SampleProject | Passed; independent restore matches deletion |
| Add nested binary and executable files | Contents and permissions survive | Passed |
| Add internal symlink | Target and link metadata survive on Air | Passed; cross-Mac defect described below |
| Rename README | Old name absent, new name preserved | Passed |
| Add fake `.env` and ignored cache | Git ignores them; backup includes them | Passed |
| Change timestamp only | Hashes match; no replacement | Passed |
| Add/change `.DS_Store` repeatedly | Finder-only difference; no repo replacement | Passed |
| Create a synthetic Git commit | Git change needs backup; history remains valid | Passed |
| Per-repo after-edit override | Only selected repo gets custom schedule | Passed |
| Change defaults after an override | Override remains independent | Passed |
| Replay an old settings revision | Reject with HTTP 409 | Passed |
| Real two-minute edit delay | Wait, then automatically replace only edited repo | Passed |
| Restart helper | Settings and archive identities persist | Passed |
| macOS upload acknowledgement | Confirmation identifies the exact current archive | Passed |
| Restore latest archive | Full file manifest and Git checks succeed | Passed |

The larger fixture produced a **50,536,544-byte archive**. Real observations included
copying, uploading, and uploaded; reported percentages progressed through approximately
6%, 34%, 62%, 77%, 87% and 99%. Upload and Air restore completed in approximately
36 seconds. No artificial network/power changes were made.

The same new archive subsequently appeared in iCloud Drive on the main Mac. The
archive was read from that Mac's iCloud folder, **not transferred over SSH**. Only the
independent Air source manifest was transferred over SSH. Both trusted SHA-256 values
matched. After the checker correction below, the main Mac restored **78 manifest
entries**, including ignored/uncommitted files and the full Git history. This establishes
real cross-device iCloud reception for this case; it is not an iCloud.com download,
a new authentication flow or a guarantee for future backups.

### Defects exposed and preserved

The first staging attempt stopped because the new staging wrapper read `status`
instead of the restore tool's actual `result` field. Its settings cleanup completed;
its failure evidence was retained. The wrapper was corrected before a fresh run.

The first main-Mac restore correctly failed `restored_manifest_mismatch`. Every
entry except `staging-link` matched: its source mode was 0700, while the receiving
Mac's default umask created it as 0755. The checker had preserved ordinary file and
directory modes but omitted setting symlink mode. The archive and baseline identities
were unchanged throughout diagnosis.

The checker fix is committed at `acf6e27`. The corrected checker sets permissions on the **symlink itself**, never its target,
and fails explicitly if the platform cannot preserve them. A regression test verifies
a different receiving umask and unchanged target permissions. The exact same received
archive and baseline then passed on the main Mac. The installed app was not modified
as part of this correction. **101 Python tests passed on both Macs** after the fix;
the original fixed app source passed 100 tests on the Air before the experiment.

### Diagnostic review and remaining UI gates

A preserved evidence snapshot contained 24 actual native menu receipts: 18 `ready`,
one `changed`, and five `uploading`, with **zero recorded input disagreements**.
Schedule events recorded `edits_not_settled` followed by `edits_settled`; archive,
upload, retention and prune events were also present. There were no app-vs-menu
same-observation comparisons, so zero disagreement must not be presented as proof
that both views agreed. The UI receipts are evidence of rendered HTML state, not
pixel/layout or accessibility verification.

The diagnostics currently **do not record the rendered progress percentage**, which
repo's expanded detail was visible, or progress-bar visibility/indeterminate state.
The private observer captures backend percentages, but does not close that gap.
Next UI instrumentation should record these fields with the same observation/archive
identity, then exercise actual native and app views. Do not approve the progress bar
solely because the backend percent increased.

The user supplied a screenshot of unnamed Finder “not responding” dialogs. A process
sample showed RepoHub's main thread idle in its normal event loop, with no blocked
app call in that sample; its stderr was empty. The dialogs were not conclusively
attributed to RepoHub. Preserve this as an unresolved visible-launch observation,
not a diagnosed app hang or a claimed UI pass.

## Remaining stages

- [ ] Record rendered percentages, indeterminate bars, visible selection and detail
      states; compare app/menu receipts against matching backend observations.
- [ ] Check visible native panel interaction, folder shortcuts, spacing and accessibility.
- [ ] Real battery manual-only behavior and plugged/unplugged transitions.
- [ ] Actual 15-minute/hourly periodic timer, sleep/wake and next-login behavior.
- [ ] Bounded failure/recovery experiments: isolated output unavailable, helper outage,
      interrupted archive build, unavailable cloud observations and stalled upload.
- [ ] Verify stale/error/unknown icons and notification suppression/recovery in real UI.
- [ ] Larger repositories, unusual Git layouts, concurrent source edits, near-full storage.
- [ ] Test the identical shipped executable separately if deployment equivalence is required.

## Leaving the staging machine

The native app and helper remain installed and running against only test repos, with
original hourly defaults and no per-repo override. Temporary one-second observation
has been stopped; the app's bounded diagnostics remain active. Case logs and fixture
archives stay private. The 48 MiB fixture remains intentionally for future tests.

To disable only this experiment, boot out the two exact Air-test labels in the logged-in
GUI domain and remove their matching test-owned plist files after preserving evidence.
Do not remove the standard application/state folders if they have since been repurposed
for real use. Do not run migration or delete personal Repository Backups as cleanup.
