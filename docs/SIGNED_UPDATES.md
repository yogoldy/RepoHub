# Coordinated packaging and signed updates

## Personal release delivery

The [October 17 delivery policy](RELEASE_DELIVERY.md) adds GitHub-hosted automatic releases after accepted main checks, current-plus-three package retention and approved update-key custody. This supersedes earlier native-before-publication requirements for Leo’s personal channel; production signing is still pending Apple activation.

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

The branch started at `d4fc605`. Packaging, native Sparkle controls, bundled-helper ownership, bounded updater diagnostics, guarded archive/appcast preparation and a rollback watchdog are implemented. [The acceptance record](SIGNED_UPDATE_ACCEPTANCE_2026-10-16.md) distinguishes the actual isolated native results from production readiness.

Developer Program purchase remains user-reported; no usable Developer ID Application certificate has been identified. Stable signing/notarization, actual permission continuity, production key/feed custody and first-install launchd migration remain open. Existing daily apps are unchanged. The personal migration installer was not run.

## Local artifact preparation

`tools/package_app.py --help` describes bundle construction. It creates a new path, requires clean source and pins all downloaded dependencies. Production builds require a Developer ID Application identity and HTTPS; disposable test identities may use a loopback feed. It does not install the bundle or register login items.

`tools/update_feed.py --help` describes archive/appcast preparation. Supply a private seed file with owner-only permissions. The compiled key matcher must confirm its public key equals the app's embedded key; no login-Keychain fallback occurs. Production artifact preparation also requires a stapled notarization ticket and Gatekeeper assessment. The tool writes local artifacts and a hash receipt; it never publishes them. Release promotion additionally requires exact-source local/GitHub acceptance.

The rollout of these coordinated bundles into legacy separate-runtime installations is not implemented by running these tools. It needs its own guarded first-install migration and deployment acceptance after stable signing. Subsequent Sparkle replacement works inside the coordinated architecture tested here.
