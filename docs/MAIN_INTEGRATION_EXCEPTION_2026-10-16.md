# One-time main integration exception — October 16, 2026

## Authorization and scope

Leo explicitly authorized a one-time exception for PR #6: integrate the existing
workspace/reliability development branch into main before the outstanding native
two-Mac validation is complete. This is code integration, not full release
approval. The exception does not authorize installation or deployment on either
Mac, mark missing evidence passed, or change the default requirements for future
releases. GitHub branch protection and the exact-head automated-contract check
remain mandatory; no bypass is authorized.

The application baseline is `686f45c` (including the information-view application
change at `ce70dbc`). The exception-record commit changes documentation only.
The clean local macOS Golden Gate for `686f45c` passed 204 Python tests with no
skips, JavaScript checks and native builds/checks. Both GitHub automated-contract
runs passed for that revision. New documentation-head checks must pass before
this PR merges. A Git merge or a green automated check does not close native
acceptance.

[PR #6](https://github.com/yogoldy/RepoHub/pull/6) records the actual merge state
and commit. Prior checkpoint statements that main promotion is blocked on the
native matrix are superseded only for this PR by this explicit exception. Their
recorded test results and open cases remain unchanged.

## Validation backlog — still required before deployment

Use [the two-Mac protocol](RELIABILITY_TWO_MAC_ACCEPTANCE.md), its fixed matrix
and the [reliability checkpoint](PRO_RELIABILITY_ACCEPTANCE.md) for exact case
requirements. Keep completed evidence separate from missing or historical cases.

- [ ] Complete the required same-candidate native matrix on both Macs. Prior
  application payload `71998b0` has partial Air evidence; it does not establish
  acceptance of the newer information view or close the Pro matrix.
- [ ] Repeat native simultaneous folder selection, alias deduplication,
  cancellation, draft removal, reviewed saves, source IDs and restart preservation.
- [ ] Verify delayed startup, failed requests, timeouts, expired client cache and
  recovery against immutable backend observations and actual displayed states.
- [ ] Complete actual isolated macOS source-access refusal, post-backup revocation,
  restoration and restart. Include root/nested reads and destination failures
  before/during backup, preservation of prior archives and independent repo progress.
- [ ] Complete unavailable/replaced-volume cases on the final candidate with the
  disposable mounted image. Physical drive hot-unplug remains outside scope.
- [ ] Complete the notification request/refusal/grant/revocation/restart lifecycle.
  A failed authorization callback is not proof of an explicit user refusal.
- [ ] Validate the installed information button/dialog, close/Escape behavior and
  Show me highlight in the native menu, correlating diagnostics with visible state.
- [ ] Before deployment, run the current clean macOS Golden Gate/current GitHub
  checks, verify candidate identity, preserve settings/backups and retain rollback.
  Deploy Pro first; verify it before considering Air deployment. Deployment still
  requires Leo's authorization.

Application changes after integration require testing the resulting final
candidate; do not reuse a previous application's matrix as evidence for new code.
Do not start this backlog or request accounts/permissions solely because it is
recorded here. Agree the next execution scope with Leo. User-reported smooth daily
operation is useful context, not a substitute for controlled acceptance evidence.

## Working folder and handoff

The sole checkout is `/Users/leogoldberg/Desktop/repos/RepoHub`. Use regular
branches there; no new worktree is authorized. Retain branch history and rollback
archives. The main RepoHub chat receives a copyable handoff from Leo; this record
does not authorize automatic cross-chat messaging. Status simplification and the
expanded-panel redesign are proposals until Leo approves their implementation.
