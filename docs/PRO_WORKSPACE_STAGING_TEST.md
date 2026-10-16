# Pro workspace-foundation staging test — 2026-10-10

## Scope and result

Tested application source `83c52bd99a8b836324994460e6a60b59a0334bd6` on the MacBook Pro using the compiled artifacts from its clean, passing macOS Golden Gate. This was a fresh isolated **runtime/state** test, not an acceptance test of the personal migration installer or a completed setup wizard. No source-picker UI exists yet: source selection used the guarded local workspace API. Native menu interactions and Finder checks used computer use.

The daily Pro installation remained `08af74f`; its application and runtime files were not replaced. The Air was not changed. Both daily launch jobs were restored and the helper reported 13 production repos with diagnostics recording. Hash comparisons before resuming confirmed that production configuration, default settings, per-repo settings, notification-status file, helper source and native executable were unchanged. Credentials were not read or changed. Test state and raw diagnostic receipts remain private, outside Git.

## Controlled inputs

- Separate temporary app bundle, bundle identifier, runtime, state, synthetic repo folders and local destination.
- Foundation home-directory probe confirmed the test home override before launching the native app.
- Two small, independent Git repos named `Project`, with distinguishable contents, ignored files and empty directories. No user repo was edited.
- Automatic schedules disabled initially. Source IDs and exact canonical paths recorded before mutations.
- Provider probe deliberately unavailable. “Awaiting confirmation” is expected after local verification; no iCloud delivery or retention deletion is claimed.
- No new login registration, token connection, issue submission, cloud account permission or production backup migration.

## Observed acceptance evidence

| Case | Evidence and result |
| --- | --- |
| Fresh repo-home state | One immediate child became a monitored workspace; diagnostics started recording. |
| Manual selection with duplicate display names | Two independent stable IDs and exact approved paths appeared in status and native cards. |
| Native manual backup | Menu action produced complete archives. Archive manifests matched source manifests, and recorded SHA-256 matched archive bytes, including Git and ignored content. |
| Unknown provider | Native cards said “Awaiting confirmation”; details said “Hashes verified · iCloud status unknown.” No uploaded/green success claim. |
| Settings through native menu | Default adapter frequency changed to hourly; battery stayed manual-only with after-edit disabled. A 30-minute adapter override saved only under the second repo's ID. Files and identities survived actual helper restart. |
| Finder bridge | The two same-named cards opened distinct approved source directories. Finder accessibility URLs confirmed each path. The manual-path click was repeated in the clean run. |
| Missing source | Moving only the first fixture caused only that card to show “Needs attention” and “Workspace folder is unavailable or its location changed.” The other card remained unconfirmed. |
| Backup with missing source | Error included the missing workspace's ID. Its prior index entry and exact archive bytes were retained. The available repo's archive was reused. |
| Recovery and real edit | Restored the first fixture, edited the second, then used the native backup action. No remaining backup error; first archive reused, second archive replaced; both complete manifests and archive hashes verified again. |
| Helper restart | Registry configuration/revision and IDs persisted; local verification resumed and native labels returned to awaiting provider confirmation. |
| Diagnostic correlation | Clean repeat recorded 215 events, one native UI client, and zero `presentation_input_disagreement` events. Events covered source configuration, scan, schedule, archive verification/reuse, scoped failure, upload observation and displayed labels. |
| Restoration | Automatic cleanup stopped test processes, restored both daily launch jobs and confirmed protected production file hashes and diagnostic availability. |

Settings/Finder observations in the first run are valid direct UI and persisted-file evidence, but its combined diagnostic stream is not accepted as single-version evidence. The clean repeat is the accepted diagnostic/missing-source/recovery evidence.

## Diagnostic discovery: stopping a parent is not isolation

The first attempt to freeze the daily helper with SIGSTOP retained its listening socket; the candidate could not bind the fixed port. Cleanup restored the daily jobs and protected files. The next attempt stopped the daily helper but froze the native parent. Its WebKit renderer continued polling the shared origin with the old presentation policy. The diagnostic stream contained multiple UI client IDs and two input disagreements on the unaffected, same-named repo.

The new candidate's independently observed native labels were correct. Fully stopping both daily launch jobs, rather than freezing the parent, removed the old UI client. Repeating the missing-source/manual-backup/recovery cases with one client produced no disagreements. This is a staging-isolation failure, not evidence of archive corruption or a confirmed candidate rendering regression. The old renderer's behavior also demonstrates why different application versions must not share a helper during acceptance testing.

Future fixed-port native staging must stop all old application surfaces, verify the old listener is gone, count presentation clients and reject unexplained clients before accepting UI/log evidence. Ensure automatic restoration even after startup failures or interruption.

## Deliberate gaps

This run does not prove real iCloud delivery, a second-device restore, destination-picker behavior, removable-volume/permission failure, sleep/login/power transitions, notification delivery, Keychain/reporting, or readable archive-name migration. Tiny archives do not establish long-running progress-bar percentages or visual smoothness. Diagnostics capture displayed status labels, not pixel rendering or selected-card/progress-percentage visibility. The personal installer was bypassed because its historical migration actions are inappropriate for this isolated fresh-state test. Product installation/setup still needs its own acceptance pass after 3B–3E exist.
