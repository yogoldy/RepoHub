# RepoHub working copy

## Canonical folder

Use `/Users/leogoldberg/Desktop/repos/RepoHub` for day-to-day development.
Use regular Git branches and commits within that folder. Do not create another
worktree unless Leo explicitly requests one. Branch changes affect the files in
this same folder, so finish/commit the current task and check for unrelated work
before switching. Preserve the protected pull-request process for main.

## Meaning of “push to Git” — agreed October 17, 2026

For RepoHub, Leo’s instruction “push to Git” authorizes completing the current
agreed feature through protected main promotion. Once the feature is complete:

1. Confirm the intended commit scope and a clean task branch. Keep unfinished or
   unrelated local work outside the candidate.
2. Run the required local checks and retain the clean Golden Gate receipt for the
   candidate. A local gate run is distinct from a GitHub Actions run.
3. Push the feature branch and create or update its pull request into main.
4. Wait for all required GitHub checks on the current PR head. Resolve failures
   within the approved scope; never bypass protection or merge a failing check.
5. Merge the passing feature through the protected PR process. No additional
   approval is needed solely because this final step moves the feature to main.
6. Report the actual merge and workflow results. Under the existing personal
   delivery policy, accepted main source can publish a Sparkle update automatically.
   Verify the feed and download when delivery is part of the task. Publishing does
   not mean an installed Mac has received or installed that version.

An explicit “local only,” “do not push,” or narrower instruction overrides this
promotion flow. Local commits and local test passes alone do not authorize a push.
Questions about whether a candidate should go to main are discussion until Leo
approves that promotion. When the instruction already covers the full flow,
continue through it without asking again after each successful check.

See [personal release delivery](RELEASE_DELIVERY.md) for automatic publication,
Apple signing limits, user-controlled installation and native acceptance evidence.

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
