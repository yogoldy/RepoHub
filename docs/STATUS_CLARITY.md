# Status clarity

How the app presents backup status: the presentation policy, menu hierarchy,
scoped report entry and information-view explanations.

## Invariants

The existing `RepoStatus.view` policy, backend backup states, schedules, archive
creation, retention, hash verification and provider observation are unchanged.
`RepoStatus.present` describes the original phase/ready result. Diagnostic policy
`status-clarity-1` independently checks the category and sentence against immutable
observations while accepting historical `change-evidence-2` clients. Cross-version
clients are not compared as if their vocabularies were identical.

Finder-only differences do not become edits. The presentation layer keeps the
internal background phase and `ready=false` for them, and the card shows the
normal green Backed up (with a Finder note in its details) once the same archive is
fresh, verified and confirmed uploaded. Upload activity referring to another archive is described as
unconfirmed, not as current-archive progress. Confirmed edits require a hash
comparison against the current saved archive and project/Git change counts.

## Validation and boundaries

Coverage includes JavaScript/Python diagnostic agreement, false-green and wrong-text
counterexamples, immutable policy checks and typed diagnostic-export privacy
coverage. The status-policy suite also checks the underlying readiness rules.

The browser preview is read-only.
It does not exercise live GitHub submission or installed native behavior.
Verify the release candidate manually in the installed app.

First-launch tutorial and interactive failure investigation remain future work.



## Menu hierarchy

Cards show identity, one category icon and a compact label. The selected panel
leads with the active explanation, then evidence, observed progress and last
created archive time. Schedule reads the existing effective per-repo policy and
power source; it never fabricates an exact next-run time. Unknown/invalid inputs
stay unavailable. Technical details preserve Finder exceptions, last hash/upload
checks and archive size. Expansion survives polling and per-repo selection.
Only actual current-archive upload activity receives a progress bar; pending,
unknown, changed and failed states do not borrow another archive's progress.

Automated coverage includes schedule policy, status presentation, report
controllers, workspace drafts and cross-language diagnostics.
Browser checks cover read-only status, expanded technical details across polls, and
580×640 and 360×640 browser layouts with no horizontal overflow or headline
clipping. These browser dimensions approximate the native footprint; they are
insufficient to verify layout in the installed WebKit view.


## Report the selected status

Report this status opens the existing glitch composer. Only fixed presentation
label/headline text is suggested for a fresh draft. It does not inject the repo
name, filesystem path, exact dates, hashes or exception prose. Existing glitch
prose is preserved when another selected status is reported; the composer shows
the newly selected status separately. Diagnostics remain optional and bounded by
the typed export contract. The exact preview and explicit Send are unchanged;
opening or checking a report does not submit anything. Sending uses the reporter's
authenticated GitHub connection.

The real shared controller regression covers both surfaces, status prefill,
private-context exclusion, existing-draft preservation, no automatic preview or
send, and the existing denied/ambiguous/explicit-send flow.

For browser verification, use a fresh synthetic helper, state directory and destination on a
separate port, with Keychain access, provider reads and external Send disabled.
Click Report this status, edit the synthetic text and prepare
a local preview with typed diagnostic attachments. Expect
Nothing sent and a disabled Send button while disconnected. Check the logs for the expected
new UI vocabulary with zero presentation disagreements and no delivery events.
The shared controller tests separately cover explicit simulated successful Send,
permission denial and draft preservation without posting a public issue.


## Status explanations and limitations

The shared information guide explains every current label, the six categories,
normal waiting, independent status freshness, the two-stage local/archive and
macOS upload process, 100%-progress uncertainty, the Finder exception and report
consent. It does not add a tutorial or claim cloud observation is a restore test.
The standalone page uses the same labels/sentences; menu layout remains primary.

Check native rendering manually in the installed app.
Failure investigation and the first-launch/repeatable tutorial are unavailable.
Status reports use the reporter's GitHub connection. There is no anonymous
submission service.



Browser coverage includes 13 controlled situations: strict success, confirmed
edits, scanning, changing-file retry, archive creation, upload at 42% and 100%,
pending confirmation, unknown upload, unavailable checks, actual failure, first
backup and Finder-only matching. The checks cover expected sentences, progress visibility and
menu-width overflow. Expected output includes all 12 distinct sentences
(upload percentages share a sentence), with zero diagnostic disagreements.
Live provider behavior and macOS permissions require separate checks.
The guide's six groups, Show me return/highlight, keyboard opening and Escape
were checked. Shared reporting tests cover preserved drafts and explicit Send;
real local preview with typed diagnostic attachments was separately exercised.

## Fixed guide header and larger reading text

With a sticky information title, guide text could
scroll above and behind it. The header is now outside the scrollable guide
body, with an opaque background and full-width divider. Layout/paint containment
prevents keyboard focus in the guide from scrolling the dialog itself. A browser
keyboard check verifies that focus remains within the scrollable body. The
dialog scroll offset should stay at zero and the title should remain visible while the body scrolls.

Reading text is larger in cards, selected details and the guide. Pending-backup
explanations and their technical sentence use green text;
icons, categories, verification and upload decisions are unchanged. This color
affects presentation only. Failure/unknown prose does not
inherit the green treatment.


Coverage includes JavaScript syntax, menu status, schedule and
guide checks, shared report-entry checks, Python status-clarity tests and
Git diff whitespace checks. Browser layout checks cover 14px main prose,
both selected sentences green, no horizontal overflow at a 611px
viewport, and keyboard scrolling of the guide with the header remaining visible.



The browser preview covers Show me and the report composer.
It does not verify report delivery, an installed update,
cross-device behavior, the full release gate or native layout.


## Specific Git and Finder descriptions

The card labels and headlines distinguish Only Finder metadata
changed, Only Git data changed, and Only Git and Finder metadata changed.
Pending differences require a complete nonnegative-integer count set from a
current-archive comparison showing zero project-file changes. Missing counts,
stale archive references, or actual project edits retain the broader wording.
The existing ignored Finder exception names the metadata difference and explains
that no new backup is needed; pending Git or metadata changes explain inclusion
in the next backup. Original phase, ready flag and backup decisions are unchanged.
Cards are taller to accommodate the longer labels; the shared information guide
explains them. Presentation policy status-clarity-2 keeps independent expected
wording, while the backend still accepts the previous status-clarity-1 vocabulary.
The typed diagnostic export permits only the fixed new labels/headlines/version.
Comparison completeness stays in the private presentation snapshot rather than
adding a field outside the diagnostic event schema.

Python regression coverage includes complete and incomplete count sets
and archive mismatch cases, original-policy preservation and legacy wording
compatibility. Additional coverage includes JavaScript syntax, menu status, schedule
and guide checks, diagnostic delivery, report entry and whitespace checks.
The diagnostic schema rejects a `repo_checked` event containing an
extra field. Comparison completeness belongs in the private snapshot.
The Finder-only card label and expanded sentence should agree.


Browser wording checks do not cover the full macOS gate or native installation.
Release qualification requires
native candidate checks and the protected promotion process.


## Conservative descriptions of metadata differences

The ignored exception's technical details say that only Finder view settings differ and explicitly
names ordinary .DS_Store files. Other metadata remains eligible for backup and
is described as file metadata. Incomplete/invalid counts or a wrong archive
produce Changes need verification, without implying an active scan. Changed
technical prose follows the guarded explanation instead of the old missing-zero
fallback. Existing view phase/ready decisions and actual backup policy are intact.
Presentation vocabulary version 3 retains prior diagnostic version support.

Coverage includes menu status, schedule and guide assertions, clarity
regressions (including unsupported-match prose) and scoped metadata backup
safety tests.


## Schedule and backup-location evidence from the helper

public_status now supplies per-repo schedule_evidence and backup_location.
The forecast copies scheduler state, restores the same saved wall-clock cadence
used by automatic_tick, and queries the unchanged plan for current eligibility.
Future due times use periodic anchors or quiet/retry eligibility; periodic
precedence is preserved when both are already due. Busy is distinct from running.
Location describes the saved archive, independently of newer source edits; cloud
confirmation needs its exact archive and a valid fresh cloud observation. The
displayed timestamp remains archive creation, never inferred upload completion.

Timing tests cover eligibility boundaries alongside the
policy and health checks. No schedule files are written by the
projection; tests assert scheduler state remains unchanged. 



## Independent timing receipts and release checks

Version 4 menu clients must identify the selected repo and provide its secondary
receipt. The helper compares location, creation date, due date, reason, countdown
minute and inclusion meaning to its original snapshot. A wrong receipt emits
timing_disagreement. Raw dates are not logged; exports accept only specific code
enums and 0–1440 whole remaining minutes. Old presentation versions remain valid.

Equivalent polls share an observation within the same displayed-minute bucket;
observed_at is not backend evidence and does not change identity. Original
snapshots remain immutable. A cross-view regression checks this invariant.
Coverage includes change-evidence tests,
timing diagnostic, privacy, selection and correlation tests, export tests and
forecast tests. The release gate requires the regressions registered under
GR06/GR07/GR09. CI discovers these tests automatically.



## Menu lines for archive location and next backup

The menu renders larger white local-creation/cloud-confirmation and next-due
lines with short due/busy/manual/blocked/unavailable variants. Cloud confirmation
still refers to the saved archive, not newer project edits; the accompanying
date is creation, not upload finish. Inclusion sentences require complete fresh
current-archive comparisons. Client timeout/cache failure suppresses cloud/time
claims. Source/hash staleness suppresses schedule claims while an independently
fresh saved-archive cloud receipt can remain visible. Countdown minutes refresh
with helper polls instead of inventing a second scheduler in the browser.

Only the selected repo's actually rendered receipt enters version 4 diagnostics;
nonselected cards do not claim secondary-line visibility. The standalone page
still reports primary states and does not claim timing-line coverage. Legacy
helpers without new evidence display unavailable rather than inferred dates.
Cross-language tests cover state/location variants, all inclusion categories,
errors, stale clients and active backups. Delivery tests verify selected identity.

