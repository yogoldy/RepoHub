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
   Six service regressions, three HTTP/security regressions and the actual JS
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

Destination changes preserve old archives in place. Existing users see a prefilled
review once, with an option to continue unchanged. Fresh users choose sources,
destination, access, schedule and review before backups can start. Discovery is
an explicit utility alongside individual selection; non-Git folders and repo-home
auto-discovery remain supported. General providers, Apple signing and Air install
are outside this update.
