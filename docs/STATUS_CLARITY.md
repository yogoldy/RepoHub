# Status clarity — implementation record

Branch: `codex/status-clarity`. Four separate commits cover presentation policy,
menu hierarchy, scoped report entry, and information-view explanations.

## Invariants

The existing `RepoStatus.view` policy, backend backup states, schedules, archive
creation, retention, hash verification and provider observation are unchanged.
`RepoStatus.present` describes the original phase/ready result. Diagnostic policy
`status-clarity-1` independently checks the category and sentence against immutable
observations while accepting historical `change-evidence-2` clients. Cross-version
clients are not compared as if their vocabularies were identical.

Finder-only differences do not become edits or strict green success. Their
informational Files match variant retains the original background phase and
`ready=false`. Upload activity referring to another archive is described as
unconfirmed, not as current-archive progress. Confirmed edits require a hash
comparison against the current saved archive and project/Git change counts.

## Validation and boundaries

Step 1 adds real-JavaScript/Python diagnostic agreement, false-green/wrong-text
counterexamples, immutable policy checks and typed diagnostic-export privacy
coverage. The original 54 status-policy checks remain unchanged.

Browser preview is read-only and separate from the installed app. No merge,
deployment, live GitHub issue submission or invasive two-Mac staging is part of
this work. Final-candidate native acceptance remains in
[the integration backlog](MAIN_INTEGRATION_EXCEPTION_2026-10-16.md).

First-launch tutorial and interactive failure investigation remain future work.
The information page's tutorial content is not being implemented in this pass.
