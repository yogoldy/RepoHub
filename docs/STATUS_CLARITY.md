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


## Step 2 — menu hierarchy

Cards show identity, one category icon and a compact label. The selected panel
leads with the active explanation, then evidence, observed progress and last
created archive time. Schedule reads the existing effective per-repo policy and
power source; it never fabricates an exact next-run time. Unknown/invalid inputs
stay unavailable. Technical details preserve Finder exceptions, last hash/upload
checks and archive size. Expansion survives polling and per-repo selection.
Only actual current-archive upload activity receives a progress bar; pending,
unknown, changed and failed states do not borrow another archive's progress.

Step 2 validation: schedule-policy assertions, original status checks, report
controller checks, workspace draft checks and cross-language diagnostics passed.
Computer use verified live read-only status, technical expansion surviving polls,
580×640 and 360×640 browser layouts with no horizontal overflow or headline
clipping. These browser dimensions approximate the native footprint; they are
not evidence of installed WebKit acceptance. Temporary viewport overrides reset.
