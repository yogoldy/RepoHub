# Backup timing and location — implementation acceptance

This is branch-level synthetic/build acceptance, not a deployed release. Both
installed Macs remain unchanged. Leo's personal event-state versus displayed-UI
review is pending and is the next discussion; do not treat this document as his
approval of wording, native behavior, main promotion or installation.

## Delivered stages

| Commit | Result |
|---|---|
| `c32c21b` | Separate ignored `.DS_Store` view settings from other file metadata; incomplete evidence cannot claim other files match. |
| `93b0fd6` | Read-only per-repo scheduler eligibility and saved-archive location projection. |
| `51a1fcc` | Independent selected-repo timing receipts, bounded exports and Golden Gate references. |
| `d180d45` | Larger white timing lines, guarded inclusion text, actual rendered selection receipts and version 4 compatibility. |
| `d3c8604` | Fix floating-clock noise that could turn a 30-minute countdown into 31. |
| `e822f10` | Consistent green expanded explanatory/technical prose, with white timing text. |

Original backup policy, ready/phase classification, archive/hash verification,
retention, request guards and saved scheduling clocks are unchanged. The
projection never writes clocks or advances the scheduler. Manual completion
still resets all periodic anchors even on failed manual runs; this pre-existing
behavior is documented, not silently changed. Forecasts honor existing periodic
precedence, per-repo overrides, edit quiet periods, retry delays and power rules.

## Event/evidence versus displayed meaning — for Leo's review

| Actual evidence / situation | Displayed meaning | Important limit |
|---|---|---|
| Only ordinary `.DS_Store` differences; ignored exception valid | Only Finder view settings changed. No new backup needed. | Informational icon; not strict byte-for-byte success. Ordinary backups still include `.DS_Store`. |
| Complete current comparison, project-file count zero, Git differs | Only Git data changed. Next backup includes changed Git data. | Missing/invalid counts cannot establish “only.” |
| Other metadata differs | Only file metadata changed; include it in next backup. | Other metadata is not disposable merely because Finder produces it. |
| Git and other metadata differ, project-file count zero | Only Git and file metadata changed. | Same completeness/current-archive requirement. |
| Incomplete or wrong-archive comparison | Changes need verification. | Does not imply a scan is running or other files match. |
| Archive created; no fresh same-archive upload receipt | Last backup created locally, with creation date. | Local creation does not establish upload completion or current local residency. |
| Fresh same-archive uploaded receipt | Latest backup confirmed in iCloud, with creation date. | Newer source edits may still be pending; date is not upload-completion time. |
| Timed or after-edit eligibility is in the future | Next scheduled check due, with due date and whole remaining minutes. | Eligibility is not a guaranteed start or completion time. Further edits can move edit-triggered eligibility. |
| Eligible now, helper free | Next scheduled check: due now. | A scan has not necessarily started; helper checks in its existing loop. |
| Eligible now, another backup holds the lock | Check due; waiting for current backup. | Do not claim active creation for this repo. |
| Manual-only policy for current power | Next backup: manual only. | Settings separately name the active power policy. |
| Actual current-repo creation | Backup in progress. | Does not claim the new archive uploaded. |
| Helper source/hash evidence stale | Next check time unavailable. | A separately fresh saved-archive cloud receipt may remain visible. |
| Client request/cache unavailable | No current location or timing claim. | Original backend snapshot is preserved; client freshness is separate. |
| No archive exists | No backup created yet. | Do not fabricate a creation date or cloud success. |

Main explanations and technical prose are green as requested. That is a reading
style across states; the unchanged icons and explicit sentences carry status.
Timing lines are white, 14px. The standalone page has primary-state receipts but
does not claim to display the new menu timing lines.

## Automated and browser evidence

Final clean macOS Golden Gate on application source
`e822f10b4e965d92aa66604baa8e3dd78faa2f9b` passed:

- 220 Python tests, zero skips; all 19 Golden Gate rules passed.
- All 20 JavaScript/native commands passed, including ARM64 native builds.
- Receipt reports clean source and unchanged source throughout the run.
- GR06/GR07/GR09 register the new timing, preservation, privacy and mismatch tests.
- Existing GitHub workflow discovers these tests; no YAML modification is needed.
- No GitHub run or protected merge was performed for these branch commits.

Private gate receipt: `/private/tmp/repohub-timing-goal-final-gate-20261016.json`.
Earlier receipt on `d180d45` passed 219 tests before the countdown regression was
added; it is superseded by the final 220-test receipt.

Browser matrix used 16 controlled situations on an isolated synthetic Git repo,
settings/state and destination: scheduled cloud, local pending, due, busy,
manual, unknown power, source blocked, edit quiet period, retry delay, creation,
stale checks, ignored Finder view settings, other metadata, Git-only, combined
Git/metadata and first backup. At 580x640 all had no horizontal overflow, correct
white timing/green explanation styles, and corresponding receipts. A 360x640
combined-metadata case also wrapped without horizontal clipping. Viewport
changes were reset. The real read-only preview separately confirmed green
success and technical prose with white timing text.

The final fixture log recorded 26 `ui_timing` receipts, all complete, zero timing
or primary-presentation disagreements, and no external report submissions.
Provider readings were synthetic, not independent iCloud retrieval evidence.
Fixture writes were limited to owned temporary state and diagnostics; no daily
sources, settings, credentials, launch jobs or installed assets were changed.
The temporary test server was stopped after evidence capture.

Private browser evidence: `/private/tmp/repohub-timing-final-browser.json`,
`/private/tmp/repohub-timing-final-preview.png`,
`/private/tmp/repohub-timing-final-narrow.png`, and
`/private/tmp/repohub-ready-green-final.png`. Raw logs and fixture sources stay
outside Git.

## Diagnostics and known limits

Version 4 menu receipts identify the selected repo and compare schedule state,
reason, saved-archive location, creation/due dates, remaining minutes and
inclusion meaning against the immutable original observation. Exact dates are
compared in memory, never emitted into shareable logs. Exports allow only fixed
codes and bounded whole minutes; malformed dates/types and missing selected
receipts fail closed. Prior presentation versions remain supported.

Polling timestamps do not become backend evidence. Equivalent polls preserve
observation identity within the displayed minute bucket; original snapshots are
not rewritten. A regression caught the initial correlation mistake. Browser
acceptance caught the countdown rounding error; the corrected candidate was
retested and passed the full gate. Diagnostics and tests are complementary;
receipts do not prove pixels or independently establish cloud delivery.

Open: Leo-led event/display walkthrough, native installed-menu scrolling and
clock display, real sleep/power/login behavior, existing two-Mac acceptance,
protected GitHub checks/PR and any installation. The read-only annotation preview
uses source assets with the older installed helper, so missing new location or
due-time fields correctly display unavailable until a coordinated helper update.
No deployment is authorized by this goal. Future public reporting, destination
selection and broader onboarding remain outside it.
