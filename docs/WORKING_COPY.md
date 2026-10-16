# RepoHub working copy

## Canonical folder

Use `/Users/leogoldberg/Desktop/repos/RepoHub` for day-to-day development.
Use regular Git branches and commits within that folder. Do not create another
worktree unless Leo explicitly requests one. Branch changes affect the files in
this same folder, so finish/commit the current task and check for unrelated work
before switching. Preserve the protected pull-request process for main.

## Consolidation — October 16, 2026

The previous menu-bar worktree held `codex/workspace-setup` at `ce70dbc`.
Both main (`08af74f`) and the older settings branch (`9f442b8`) were ancestors
of that commit: neither held missing changes requiring a merge into development.
All three working trees were clean; the menu-bar worktree's ignored files were
Python caches. The older settings worktree had no ignored files.

The development branch was moved into the canonical folder. Before retiring the
two additional worktrees, all branches were preserved in a verified Git bundle
and both extra folders were archived, including ignored files. A digest of all
tracked file paths and contents matched before and after the move. Existing
branches and history remain available. Main was not merged or moved.

The old additional working folders were:

- `/Users/leogoldberg/.codex/worktrees/repohub-menu-bar/RepoHub`
- `/Users/leogoldberg/.codex/worktrees/repohub-settings/RepoHub`

Those paths are historical and must not be used for new work. Start future
commands and editor sessions in the canonical folder. The temporary annotation
preview is redirected there; installed apps, helper configuration, credentials,
schedules and backups are not part of this migration.

This is a checkout consolidation, not release acceptance. The pending reliability
acceptance and protected main promotion retain their existing requirements.
