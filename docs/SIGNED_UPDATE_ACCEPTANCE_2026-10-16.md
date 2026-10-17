# Signed update acceptance — October 16, 2026

## Scope and source

Application payload: `ad29dc9b9f9cff5675d02086bf65147c8fa70a96`, on `codex/signed-updates`. Later feed-tool, test and documentation commits do not change the accepted app/helper/web modules. This is isolated Pro acceptance, not a deployed daily release. No Air operation, personal migration installer, permission reset or production key creation occurred.

The native app, Sparkle 2.10.0, standalone CPython 3.14.8, helper modules, cloud-status and web assets reside in one signed test bundle. Dependency hashes are pinned in `tools/update-dependencies.json`; the bundle resource manifest and HTTP helper identity must agree before the menu loads. Settings and repository archives remain outside it.

## Verified results

| Case | Result and evidence |
|---|---|
| Complete package | Built and verified with codesign; standalone Python launched the actual helper without Homebrew. Native integrity regressions reject altered, missing, extra and escaping resources. |
| Signature refusal | Actual Sparkle dialog refused a deliberately wrong signature. Running build stayed unchanged. Repeated on the corrected application source. |
| Truncated download | Actual Sparkle validation rejected a 100,000-byte fragment against the full signed archive. Running build stayed unchanged. Repeated on corrected source. |
| Valid replacement | Native Settings → Check for Updates → Install Update → Install and Relaunch replaced the test bundle and started matching helper/UI. Corrected-source builds 103 → 104 passed; watchdog receipt says healthy. |
| Equal-version offer | Actual native dialog said up to date. A reproduced false-failure diagnostic was fixed; corrected source reports `ready / no_update` after dismissal. |
| Busy backup | A real synthetic archive was active; native Check for Updates refused with the running-backup explanation. Diagnostics reported `waiting / backup_busy`. Backup completed without errors. |
| Shutdown race | A real helper subprocess received SIGTERM while a controlled snapshot held the backup lock. It stayed alive until publication completed, then exited cleanly. New archive hash and predecessor preservation were checked. |
| Failed replacement | Correctly signed fault-injection build 105 deliberately exited before helper startup. The independent watchdog restored build 104, relaunched its helper, and recorded restored. Earlier prototype 102 → 101 recovery also passed but does not substitute for the corrected-source repeat. |
| Data preservation | Synthetic config, workspace registry, schedule settings and verified archive hashes matched before/after replacement and rollback. The larger busy-backup fixture and its archives were removed only during explicit disposable-test cleanup. |
| Daily isolation | Daily native executable, external helper, configuration and workspace-registry hashes matched before/after. Daily helper still served 13 repos on its normal port; isolated test port and feed were stopped. No launch registration was changed. |
| Keys and feed tooling | Ephemeral file-only EdDSA key; no daily Keychain access. Saved feed tool prepared and verified the signed archive; compiled key matching rejected a foreign key. Ephemeral private key removed during cleanup. |
| Diagnostics | Typed updater phase/reason fields and matching-release guards passed privacy regressions; arbitrary paths/prose rejected. Watchdog outcomes remain bounded local receipts, not an update-history UI. |

Test builds used ad-hoc Apple code signatures and a separate EdDSA archive key. These tests do not prove Developer ID identity continuity, notarization or macOS permission retention.

## Automated checks

Clean macOS gate on application source `ad29dc9`: 230 Python tests passed, with JavaScript, native integrity/outcome checks and a complete Sparkle-linked signed bundle build. Later feed regressions, compiled key-matching checks and final documentation-head GitHub status are separate finalization checks; inspect their exact-head receipts rather than inheriting this count.

The existing GitHub YAML already invokes `tools/release_gate.py`. That gate now builds the actual coordinated Sparkle package and runs native resource/key checks, in addition to discovered Python regressions. GR20 records the new failure boundary; no new test runner or uploaded CI artifact was required.

## Diagnostics found and fixed

- Foundation resource URLs and file enumerators use different `/var` versus `/private/var` spellings. Compare actual filesystem paths; do not weaken integrity checks to work around aliases.
- Test sources inside the state folder conflict with the registry's overlap protections. Use sibling source/state/destination folders under the isolated identity.
- Sparkle reports no-update and cancellation through error-shaped callbacks. Those are normal outcomes; genuine signature/download failures remain failures.
- A Quit tooltip inherited from the separate launchd helper was inaccurate for owned bundled helpers. Corrected text says an active backup finishes before quitting.

## Remaining release work

- Developer Program activation and a usable Developer ID Application certificate.
- Stable signing/notarization, production EdDSA key custody and an HTTPS feed. No production feed was published and no production private key was generated.
- Guarded first-install migration from existing separate runtime/launchd services. New artifact tools deliberately do not execute the personal migration installer or change current registrations.
- Actual permission-continuity upgrade, then the applicable Pro/Air release acceptance and protected promotion. No claim that old native-validation backlogs are closed by these update tests.
- Recovery currently retains a private bounded receipt and returns to the previous app. A persistent user-facing recovery explanation/history has not been implemented.

The goal remains open. The checked local update mechanism is not deployment approval.

## Private evidence and cleanup

Private acceptance workspace: `/private/tmp/repohub-real-upgrade`. It contains native error/up-to-date/busy screenshots, preservation hashes, signed test artifacts and retained diagnostic logs. `retained/acceptance-evidence.json` records watchdog outcomes; `retained/RepoHub Test.app` is the verified recovered rollback bundle. Raw logs, personal paths and signing keys are not committed.

The separate test app/helper and loopback feed were stopped. The disposable identity's source/state/destination and defaults were removed after preservation checks; large synthetic backups therefore do not remain in the daily destination. Retained test bundles are evidence only and no longer have a live test configuration. Your daily Pro app remains the earlier installed version, and the Air is unchanged.
