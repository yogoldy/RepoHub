# First-run setup implementation

Approved October 18, 2026. Work proceeds on `codex/product-roadmap-refresh` in
separate tested commits before protected promotion and installed-Mac acceptance.

## Stages

1. **Integrated:** readable layout planning and a recoverable rename
   transaction. IDs remain metadata; duplicate names gain distinguishing parent
   folders. Four controlled regressions cover interrupted staging/publication,
   partial configuration writes, swaps, foreign targets and symlink rejection.
   The runtime uses this mapping after explicit reviewed apply.
2. **Integrated:** one iCloud destination with physical identity,
   helper-owned write probe, free-space and source/state separation checks. Three
   controlled regressions cover aliases, overlap, disk full and replacement or
   disappearance without path recreation. The native picker is connected.
3. **Integrated:** bounded, cancellable recursive Git candidates,
   with explicit incomplete results and unsupported external Git stores. Synthetic
   tests exercise nested/invalid/external repos, protected folders, loops, limits,
   missing Git, cancellation and permission failures. Selection remains draft-only.
4. **Integrated:** a separate five-step welcome window,
   native pickers, idle fresh bootstrap and reviewed transactional setup. Existing
   installs can continue unchanged. Async access/review/apply operations retain
   draft and revision guards. The runtime uses the saved layout, rechecks physical
   destination identity and retains old-location archives when switching roots.
   Nine service regressions, four HTTP/security regressions and the actual JS
   controller exercise explicit saves. Native app compilation and unique-test
   bootstrap/restart checks passed. Native evidence is recorded below.
5. **Integrated contract:** GR23–25 register executable setup,
   destination/migration and discovery regressions. Typed events are allowlisted
   for shared exports without source/destination names or review fingerprints.
   The existing macOS PR/main/release gate includes the new regressions and native
   checks; workflow triggers and protected main policy remain unchanged. Release
   PRs carry the exact candidate gate and post-publication installed results.

## Validation notes

The first broad run executed 300 tests: 299 passed; a native disposable UserDefaults
cross-process read failed under the restricted environment. The same five native
appearance tests passed when run with their required disposable-domain access.
This does not replace the final clean-source macOS gate. Other focused passes
include all 20 existing workspace tests, seven package-selection tests, the native
app build, native fresh bootstrap/restart and the setup/API/controller tests.

The clean macOS gate at `236b3b5` passed 304 tests, 25 rules and 30 commands
with unchanged source. An isolated native pilot then selected a non-Git folder,
discovered/reviewed two same-named nested Git repos, chose a test destination,
checked access and finished without creating any archives. An explicit native
backup verified all three archive manifests and checksums. It also exposed the
old flat-directory retention guard rejecting the two grouped paths after safe
publication. No archives were lost. A new regression now exercises latest-only
retention in nested groups, withholding cleanup until exact upload evidence and
protecting sibling archives. Final native repeat and a new gate are required.

The corrected isolated bundle at `da9c213` restarted with all three selected
sources and the saved schedule intact, with setup already reviewed. A guarded
explicit backup request then completed with no errors: all three archive
checksums and source/archive manifests matched, including both parent-grouped
paths. The test destination correctly remained upload-unconfirmed; no real
iCloud delivery is claimed. The temporary app has a separate identity/state/port.
The daily app has not been changed during this pilot.

The actual welcome controller also tests two consecutive discovery runs: Cancel
must become available on every scan, old result controls are cleared while
scanning, and newly selected Git candidates retain the existing non-Git source.
A draft destination is included in the scan exclusions before it is saved.

The first-backup counterexample also covers the shared health/status boundary:
before an archive exists, a fresh source scan shows First backup pending and
cannot generate a stalled-upload episode. Once an archive exists, upload
freshness remains required. The test renders the actual JS policy from real
helper output and never permits a green backed-up state without upload evidence.
Apply also rejects a replaced source identity before probing the replacement's
contents. Access checks revalidate each source after probing, and destination
checks compare the reviewed identity before their temporary write probe.

Destination changes preserve old archives in place. Existing users see a prefilled
review once, with an option to continue unchanged. Fresh users choose sources,
destination, access, schedule and review before backups can start. Discovery is
an explicit utility alongside individual selection; non-Git folders and repo-home
auto-discovery remain supported. General providers, Apple signing and Air install
are outside this update.

## Published and installed acceptance

The clean macOS gate at `890e3a5` passed 307 Python tests, 25 rules and 30 commands,
with unchanged source and no skipped tests. [PR #11](https://github.com/yogoldy/RepoHub/pull/11)
passed both branch checks, merged through protected main at `7203412`, passed the
main gate and automatically published RepoHub 0.0.5 build 5. The live feed,
download length, archive SHA-256 and Ed25519 signature matched the receipt.

The existing Mac updated from 0.0.4 through Sparkle. App and helper reported the
published revision; five saved configuration/settings/clock files and fifteen
current archive hashes were unchanged before setup. The welcome window opened
with the existing repo-home selection. Native discovery found both isolated Git
fixtures, unchecked, while all fourteen daily sources stayed active and unchanged.
The native destination picker selected the existing iCloud root. Helper-observed
access passed; the existing 60-minute battery and 240-minute adapter schedules,
after-edit settings and per-repo overrides were retained.

Explicit Finish setup renamed all fifteen managed archive paths without changing
their hashes, workspace IDs, sources, settings or clock. It started no backup and
left no recovery journal. Fresh macOS observations reported uploaded at the new
paths for all fourteen workspaces. This is actual iCloud evidence, separate from
the isolated test destination's unconfirmed upload state. Private baseline and
post-apply evidence remain outside Git.

This installed check also found that Reload saved settings did nothing: its
JavaScript confirmation was not hosted by the native welcome window. A controlled
controller regression reproduced the failure. Reload now directly discards only
the draft, clears old discovery/access/completion UI, and never calls apply. It is
disabled while a native picker or discovery is active. The follow-up release PR
must record its own clean gate, Sparkle install, native reload and explicit backup
acceptance. Real permission denial/recovery was not forced on the daily app;
Apple signing/notarization, other providers and Air remain outside this update.

The first follow-up PR check passed, while its duplicate branch run failed the
cancellation regression. Investigation reproduced a real late-cancellation race:
the worker could accept cancellation during its final check, then report complete.
An event-controlled regression now fixes that timing independently of runner
speed and requires cancelled/incomplete state plus the existing partial diagnostic.
Both corrections stay in the same protected follow-up release; the failed run is
not accepted as release evidence.
