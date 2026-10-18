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
3. **Pending:** recursive, cancellable Git discovery and reviewed selection.
4. **Pending:** isolated fresh startup, welcome window, transactional setup and
   runtime integration, preserving existing configuration until explicit apply.
5. **Pending:** diagnostics, Golden Gate/CI, release and installed acceptance.

Destination changes preserve old archives in place. Existing users see a prefilled
review once, with an option to continue unchanged. Fresh users choose sources,
destination, access, schedule and review before backups can start. Discovery is
an explicit utility alongside individual selection; non-Git folders and repo-home
auto-discovery remain supported. General providers, Apple signing and Air install
are outside this update.
