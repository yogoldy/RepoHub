# Native source-picker acceptance — 2026-10-10

## Installed build and controlled test

The Pro runs application commit `5e240097aab02f75336e1bed6fcc738b108d8d11` from `codex/workspace-setup`. Its clean macOS Golden Gate passed 165 Python tests with zero skips, JavaScript syntax/status/diagnostic/workspace-draft checks, native/cloud builds and native bridge/readiness checks. GR16 requires review-drift, preservation, guard/privacy and unmonitored-home inventory-drift regressions. Main was not merged, and the Air was not deployed.

Computer use tested native menus and `NSOpenPanel` on isolated fresh state before daily deployment. Two same-named synthetic Git repos at separate local paths included ignored files and empty directories. A third immediate child was introduced after review to force a conflict. Both daily launch jobs were fully stopped during isolation and unconditionally restored; no prior WebKit clients shared the test helper. Test-owned local destinations had no provider signal, so their uploads remained unconfirmed. Raw case paths, logs and receipts remain private outside Git.

## Native cases and diagnostic evidence

- Opened the gear → **Choose repo folders**; both mode descriptions and paths were accessible.
- Opened the repo-home folder picker and cancelled. The UI confirmed cancellation and retained the draft; no save occurred.
- Chose the containing fixture folder through the native picker; reviewed its immediate child and exact canonical path.
- Added a child after review; **Save monitored folders** rejected the stale review. **Reload current selection** exposed both children for a fresh review before save.
- Saved the reviewed home selection; switched to individual folders, removed the added child from the draft and selected a same-named repo at another location.
- Reviewed both canonical paths and the explicit **Stop monitoring** list, then saved. Original repo ID was retained; the additional same-named repo had an independent ID. The removed source directory was left intact.
- Used native **Back up now**. Both source/complete-archive manifests matched, including Git and ignored content; recorded SHA-256 matched archive bytes. No provider-upload claim was made.
- Restarted the helper; the UI-saved configuration and revision persisted.
- The full picker run at `6bce180` recorded three `workspace_review` and two successful `workspace_configuration` events with no raw source paths and no `presentation_input_disagreement` events.
- The final build additionally records rejected saves. A controlled stale-revision request returned 409 and logged `workspace_configuration: failed`; the subsequent native reviewed save logged `saved`. Final live checks had no status disagreements and returned immediately to refreshed cards.

Folder choice and review do not start a backup; the test's manual backup was a separate explicit action. Removing monitoring does not erase archives or saved schedules, as mandatory regressions independently verify.

## Failure found during native testing

The first candidate (`a4db1b1`) drew a new modal after closing Settings, but WebKit's native accessibility tree did not expose the modal controls. A screenshot showed the screen while the accessibility tree lacked buttons, making computer-use and assistive navigation unreliable. Source setup now reuses the existing settings dialog, swapping forms and accessible title, rather than opening a second top-level modal. At `6bce180`, the native controls, picker, cancel return and review/save were visible in accessibility and usable. Cancel and successful save restore the normal settings form. This is live UI evidence, not a claim that backend logs detect missing accessibility nodes.

The acceptance run also showed cards waiting for the normal polling interval after save. The final change requests an immediate status reload and logs rejected selection saves, while keeping those logs free of paths or exception prose. An additional regression changes the contents of an unmonitored candidate home while the current registry stays unchanged, proving that the review fingerprint protects more than registry revision alone.

## Daily deployment and safety checks

Installed only on the Pro with a recoverable app/runtime rollback copy. Verified 27 installed/runtime/served assets against the gated source, native signature/binary identity, preserved config/default schedules/per-repo schedules, 13 migrated stable source identities and diagnostics recording. Existing iCloud archives were not renamed or manually deleted. The registry migration creates app-owned configuration and preserves the legacy source IDs; subsequent startup verification can temporarily show checking/verifying states.

One deployment probe initially looked for a JavaScript-generated label in static HTML. It failed, and the deployment rolled back. The corrected probe verifies the static setup form, the dynamic label in the served JavaScript and exact asset hashes. The successful retry retained rollback evidence; this was a verification-script error, not an application delivery failure.

Computer use then opened the **installed daily app**, inspected preserved hourly battery/four-hour adapter defaults, opened source setup, reviewed all 13 exact existing paths, and cancelled. No production selection was saved. The helper's private diagnostics recorded the 13-repo review; sources and schedules remained unchanged. Credentials were neither read nor changed; this was not a new Keychain/report-delivery acceptance test.

## Remaining acceptance and scope

Native selection was exercised across separate picker sessions; one-panel simultaneous multi-selection and external-volume/permission failure remain live coverage gaps. Empty/manual removal, path deduplication, overlap rejection, stale revision, candidate drift and backup/JSON/schedule preservation have automated coverage. This pass does not test a new iCloud delivery, second-device restore, sleep/power transitions or long progress percentages. Destination selection/status, guided onboarding, readable archive names and AI-assisted import remain later roadmap items. The main protection/PR process remains in force.
