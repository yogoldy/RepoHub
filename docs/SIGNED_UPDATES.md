# Coordinated packaging and signed updates

## Authorized goal

Work on `codex/signed-updates`, in the existing checkout. Build one coordinated app version, add Sparkle's Check for Updates, and validate actual upgrades using disposable apps. Daily Pro and Air installations, launch registrations, permissions, settings and backups stay untouched. Developer ID signing and permission continuity remain pending membership activation and a usable certificate.

## Release boundary

A replacement app contains the native executable, Sparkle framework, pinned standalone Python, helper modules, cloud-status executable and web interface. Application resources are immutable. Settings, workspace registry, schedules, credentials and archives remain outside the bundle. No personal migration installer runs during packaging or update testing.

An immutable release manifest identifies the source revision, application version, build number and component hashes. Missing or inconsistent components must fail before the helper starts. Runtime dependency downloads are pinned by SHA-256 and retain their licenses. Test apps use a separate bundle identifier, configuration, state, destination and loopback port; they must not register daily login items.

Sparkle authenticates downloaded archives with its EdDSA public key. This is separate from Apple's Developer ID signature. Production feeds require HTTPS; loopback HTTP is allowed only for disposable test identities. Private update keys never enter Git. No production key is created by this work without an explicit key-custody checkpoint.

## Staged work

1. Record this contract and acceptance matrix.
2. Add coordinated bundle construction and integrity checks, with synthetic regressions.
3. Add bundled-helper lifecycle, explicit component identity and Sparkle integration.
4. Add signed-feed tooling and run real isolated upgrade/failure tests.
5. Extend diagnostics and Golden Gate/CI checks; commit final evidence and open dependencies.

Each narrow change is committed separately. Any application change invalidates earlier candidate acceptance. A clean Golden Gate receipt establishes automated evidence, not native acceptance or permission continuity.

## Acceptance matrix

| Case | Required evidence |
|---|---|
| Complete package | Exact source and component hashes; pinned Python runs without Homebrew; native binary links the embedded framework. |
| Incomplete/mixed package | Missing, altered or foreign components stop helper launch with a bounded diagnostic reason. |
| Isolation | Unique app identity and state/port; daily app, configuration, launch registrations and archives unchanged. |
| Successful upgrade | Actual Sparkle check downloads and verifies a signed older-to-newer test release, replaces the bundle and relaunches the matching helper/interface. |
| Invalid update | Invalid signature, truncated download and non-increasing version cannot replace the accepted app. |
| Backup coordination | An active backup prevents replacement; installation proceeds safely after it finishes. |
| Failed startup | Detect unhealthy replacement; retain and demonstrate a usable rollback without touching protected state. |
| User controls | Native Check for Updates works; cancel/no-update/error messages are visible and truthful. |
| Diagnostics | Bounded update phase/reason and component identity; no paths, private keys or exception prose in shareable evidence. |
| Production identity | Developer ID signing, notarization and an actual permission-retention upgrade; blocked until the certificate is available. |

## Stopping points

Stop promotion for any failed case. Continue narrow fixes and retests. Stop for user input if credentials, broader permissions, signing-key custody or inaccessible native controls require it. Never reset daily permissions. Restore owned test services before reporting a blocker. No merge or daily installation is implied by this goal.

## Current evidence

2026-10-16: branch starts at `d4fc605`; no updater implementation or native acceptance yet. Developer Program purchase is user-reported; no usable Developer ID Application identity was found. Existing separate runtime packaging caused a failed preview installation and rollback; the installed daily app remains the older version. This goal addresses coordinated replacement, not backup-status logic.
