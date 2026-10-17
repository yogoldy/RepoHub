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

## Pro test installation after implementation

Leo subsequently authorized a Pro-only preview installation to try the work.
[The deployment record](PRO_STATUS_CLARITY_PREVIEW_2026-10-16.md) identifies the
installed application source, preserved configuration, guarded rollback finding,
actual native smoke evidence and remaining checks. This supersedes the earlier
no-deployment implementation scope only for that explicit Pro test installation;
it does not close two-Mac acceptance or authorize an Air deployment.


## Pro visual feedback — fixed guide header and larger reading text

Leo reported that the installed information title stayed visible but guide text
scrolled above and behind it. The header is now outside the scrollable guide
body, with an opaque background and full-width divider. Layout/paint containment
prevents keyboard focus in the guide from scrolling the dialog itself. A browser
keyboard check caught that second failure before containment was added; the
repeat kept dialog scroll at zero and the title in place while the body scrolled.

Reading text is larger in cards, selected details and the guide. Pending-backup
explanations and their technical sentence use the requested green treatment;
icons, categories, verification and upload decisions are unchanged. This color
is a visual experiment, not new success evidence. Failure/unknown prose does not
inherit the green treatment. The proposed Git/Finder-specific label change
remains unimplemented.

Validation: JavaScript syntax, 54 original menu status checks plus schedule and
guide checks, shared report-entry checks, four status-clarity Python tests and
git diff whitespace checks passed. Browser checks confirmed 14px main prose,
both selected sentences green, no horizontal overflow at the current 611px
viewport, and keyboard scrolling of the guide with the header remaining visible.
Private screenshots are outside Git. The supplied screenshots established the
reported problem; reviewing the OBS recording was unnecessary.

Leo reports Show me works and the report composer UX looks good; he did not
verify delivery in this review. These changes are preview-only: no installed
app update, Air operation, full Golden Gate or native acceptance was performed.


## Specific Git and Finder descriptions — October 16, 2026

The approved card/headline wording now distinguishes Only Finder metadata
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
adding an unapproved field to existing diagnostic events.

Validation: 210 Python tests passed, including explicit complete/incomplete count
and archive mismatch cases, original-policy preservation and legacy wording
compatibility. JavaScript syntax, original 54 menu status checks plus schedule
and guide checks, diagnostic delivery, report-entry checks and whitespace checks
passed. The first full run exposed a rejected repo_checked event caused by an
extra field; keeping it private fixed the failure and the full repeat passed.
Browser review confirmed the live Finder-only label, matching expanded sentence,
no clipped card labels and no horizontal overflow at 611px. Private screenshot:
/private/tmp/repohub-metadata-label-review.png.

No full macOS Golden Gate, native installation or Air changes were made in this
wording pass. Both installed apps retain their previous versions; native final-
candidate acceptance and protected release promotion remain open.


## Timing goal stage 1 — conservative descriptions

The ignored exception now says Only Finder view settings changed and explicitly
names ordinary .DS_Store files. Other metadata remains eligible for backup and
is described as file metadata. Incomplete/invalid counts or a wrong archive
produce Changes need verification, without implying an active scan. Changed
technical prose follows the guarded explanation instead of the old missing-zero
fallback. Existing view phase/ready decisions and actual backup policy are intact.
Presentation vocabulary version 3 retains prior diagnostic version support.

Stage validation: original menu status/schedule/guide assertions, six clarity
regressions (including unsupported-match prose) and scoped metadata backup
safety tests. No installation. Leo’s event-state versus displayed-UI review
remains a required follow-up after the combined implementation is validated.


## Timing goal stage 2 — helper evidence

public_status now supplies per-repo schedule_evidence and backup_location.
The forecast copies scheduler state, restores the same saved wall-clock cadence
used by automatic_tick, and queries the unchanged plan for current eligibility.
Future due times use periodic anchors or quiet/retry eligibility; periodic
precedence is preserved when both are already due. Busy is distinct from running.
Location describes the saved archive, independently of newer source edits; cloud
confirmation needs its exact archive and a valid fresh cloud observation. The
displayed timestamp remains archive creation, never inferred upload completion.

Four new timing tests (including a broad eligibility boundary matrix) and all
33 existing policy/health tests passed. No schedule files are written by the
projection; tests assert scheduler state remains unchanged. The interface does
not consume these fields until the later UI commit. No deployment performed.


## Timing goal stage 3 — independent secondary receipts and release rules

Version 4 menu clients must identify the selected repo and provide its secondary
receipt. The helper compares location, creation date, due date, reason, countdown
minute and inclusion meaning to its original snapshot. A wrong receipt emits
timing_disagreement. Raw dates are not logged; exports accept only specific code
enums and 0–1440 whole remaining minutes. Old presentation versions remain valid.

Equivalent polls share an observation within the same displayed-minute bucket;
observed_at is not backend evidence and does not change identity. Original
snapshots remain immutable. A cross-view regression caught and corrected an
initial violation of this rule. Nine existing change-evidence tests, the new
timing diagnostic/privacy/selection/correlation tests, nine export tests and
four forecast tests passed. Critical new tests are registered in Golden Gate
GR06/GR07/GR09. The workflow already discovers them, so YAML is unchanged.
The UI will opt into version 4 in the next stage. No deployment.


## Timing goal stage 4 — evidence-driven menu lines

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
No daily state or installed assets are changed by this commit. Final browser and
clean macOS Golden Gate evidence is recorded in the following acceptance stage.


## Timing goal acceptance checkpoint

[The acceptance record](BACKUP_TIMING_ACCEPTANCE_2026-10-16.md) lists staged
commits, the event/evidence-to-display matrix, final 220-test clean macOS gate,
16-case browser/diagnostic evidence, countdown correction and open native work.
Leo's informed-ownership review of actual event states versus displayed meaning
is explicitly next and remains pending. Neither Mac was deployed.
