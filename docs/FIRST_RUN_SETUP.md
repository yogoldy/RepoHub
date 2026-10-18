# First-run setup implementation

Approved October 18, 2026. Work proceeds on `codex/product-roadmap-refresh` in
separate tested commits before protected promotion and installed-Mac acceptance.

## Stages

1. **Implemented component:** readable layout planning and a recoverable rename
   transaction. IDs remain metadata; duplicate names gain distinguishing parent
   folders. Four controlled regressions cover interrupted staging/publication,
   partial configuration writes, swaps, foreign targets and symlink rejection.
   This component is not yet connected to the daily runtime.
2. **Implemented component:** one iCloud destination with physical identity,
   helper-owned write probe, free-space and source/state separation checks. Three
   controlled regressions cover aliases, overlap, disk full and replacement or
   disappearance without path recreation. Runtime/picker integration is pending.
3. **Implemented component:** bounded, cancellable recursive Git candidates,
   with explicit incomplete results and unsupported external Git stores. Synthetic
   tests exercise nested/invalid/external repos, protected folders, loops, limits,
   missing Git, cancellation and permission failures. Selection UI is pending.
4. **Implemented, acceptance pending:** a separate five-step welcome window,
   native pickers, idle fresh bootstrap and reviewed transactional setup. Existing
   installs can continue unchanged. Async access/review/apply operations retain
   draft and revision guards. The runtime uses the saved layout, rechecks physical
   destination identity and retains old-location archives when switching roots.
   Seven service regressions, four HTTP/security regressions and the actual JS
   controller exercise explicit saves. Native app compilation and unique-test
   bootstrap/restart checks passed. Native picker/layout acceptance is pending.
5. **Implemented contract; acceptance pending:** GR23–25 register executable setup,
   destination/migration and discovery regressions. Typed events are allowlisted
   for shared exports without source/destination names or review fingerprints.
   The existing macOS PR/main/release gate includes the new regressions and native
   checks; workflow triggers and protected main policy remain unchanged. A clean
   full gate receipt, isolated native interaction and installed update are pending.

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

Destination changes preserve old archives in place. Existing users see a prefilled
review once, with an option to continue unchanged. Fresh users choose sources,
destination, access, schedule and review before backups can start. Discovery is
an explicit utility alongside individual selection; non-Git folders and repo-home
auto-discovery remain supported. General providers, Apple signing and Air install
are outside this update.
