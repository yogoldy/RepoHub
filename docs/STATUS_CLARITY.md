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


## Step 3 — report the selected status

Report this status opens the existing glitch composer. Only fixed presentation
label/headline text is suggested for a fresh draft. It does not inject the repo
name, filesystem path, exact dates, hashes or exception prose. Existing glitch
prose is preserved when another selected status is reported; the composer shows
the newly selected status separately. Diagnostics remain optional and bounded by
the typed export contract. The exact preview and explicit Send are unchanged;
opening or checking a report does not submit anything. This retains the current
owner GitHub connection, not a public submission service.

The real shared controller regression covers both surfaces, status prefill,
private-context exclusion, existing-draft preservation, no automatic preview or
send, and the existing denied/ambiguous/explicit-send flow.

Step 3 browser validation used a fresh synthetic helper/state/destination on a
separate port, with Keychain access, provider reads and external Send disabled.
Clicked the actual Report this status button, edited synthetic prose and prepared
the real local report preview with typed diagnostic attachments. It showed
Nothing sent; disconnected Send remained disabled. Logs recorded the expected
new UI vocabulary with zero presentation disagreements and no delivery events.
The shared controller tests separately cover explicit simulated successful Send,
permission denial and draft preservation; no public issue was posted.


## Step 4 — explanations and remaining work

The shared information guide explains every current label, the six categories,
normal waiting, independent status freshness, the two-stage local/archive and
macOS upload process, 100%-progress uncertainty, the Finder exception and report
consent. It does not add a tutorial or claim cloud observation is a restore test.
The standalone page uses the same labels/sentences; menu layout remains primary.

Required native two-Mac acceptance remains explicitly open. No installed app,
launch registration, real workspace, schedule or backup destination is changed.
Failure investigation and the first-launch/repeatable tutorial remain backlogged;
the status report is the existing owner-authenticated reporting flow, not a public
submission service. Final clean Golden Gate receipt is generated after this
commit and retained privately; the final report states its actual outcome.


Final browser evidence used 13 controlled situations: strict success, confirmed
edits, scanning, changing-file retry, archive creation, upload at 42% and 100%,
pending confirmation, unknown upload, unavailable checks, actual failure, first
backup and Finder-only matching. All expected sentences, progress visibility and
menu-width overflow checks passed. The fixture logged all 12 distinct sentences
(upload percentages share a sentence), with zero diagnostic disagreements.
Real provider/permission behavior was not simulated into an acceptance claim.
The guide's six groups, Show me return/highlight, keyboard opening and Escape
were checked. Shared reporting tests cover preserved drafts and explicit Send;
real local preview with typed diagnostic attachments was separately exercised.
