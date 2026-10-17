# Personal RepoHub update delivery

## Agreed policy — October 17, 2026

Leo approved easy delivery to his own Macs: a protected main merge with a passing automated Golden Gate may publish an update; installed-Mac testing follows delivery. It is not a claim that every native interaction has been validated. Keep the outstanding native reliability matrix and signing/permission evidence visible. Do not add an unstated native approval prerequisite to personal delivery. This supersedes the earlier pre-delivery native acceptance requirement for this personal updater channel only; it does not authorize bypassing main protection, publishing failed checks or silently installing daily apps.

## Automatic path

`Golden rules` completes for a main push → `Publish signed update` checks the same source → packages/signs → Apple notarization accepts → staple ticket → Sparkle archive signature verifies → upload draft → download and compare every asset → recheck current main → publish as latest → confirm latest → retain four managed release packages.

The release job is opt-in through `REPOHUB_RELEASE_ENABLED=true`. It is currently **false**. A fork, pull-request run, failure, stale main commit or missing `automated-contract` success is rejected. It checks out the triggering full SHA, not a moving branch, does not consume artifacts or caches from untrusted runs, and reruns the clean macOS gate before exposing signing secrets to the packaging step. The publishing job has contents-write/actions-read access; other jobs keep read-only access. Jobs serialize, and a newer main commit supersedes a still-packaging older candidate.

GitHub Releases hosts public downloads. No new paid hosting service or Actions artifact storage is used. The stable Sparkle URL is:

`https://github.com/yogoldy/RepoHub/releases/latest/download/appcast.xml`

Each release contains a version-specific ARM64 ZIP, appcast and public receipt with source SHA/build/archive hash. `latest` changes only after the draft's uploaded bytes match the verified local artifacts. Before that point, failures leave the existing feed alone. If post-publication confirmation fails, cleanup stops; the log must not call uncertain publication a success. Failed drafts stay unpublished for inspection and reserve their build number. Other manually published releases in this repository must use `--latest=false` so they cannot redirect this feed.

## Versions and recovery

The first release is `0.0.1` / build 1. Successful or reserved draft builds increase monotonically: `0.0.9` → `0.1.0` → `0.1.1`. Tags are `repohub-v<version>-b<build>` and point to the exact accepted source. Re-running an already-published source does not publish it twice. No source files are modified to bump versions.

Keep the current package plus **three previous published managed packages**, approximately 114 MB at the currently measured 28.5 MB per archive. Cleanup runs only after confirmed publication. It validates all deletion candidates' production receipts and source tags before deleting any release; unrelated releases, drafts, tags, Git history, repository backups and local rollback copies are untouched. Old Git tags remain even when their downloadable package is removed. Failed-draft cleanup is deliberate/manual, not part of automatic retention.

To roll back, restore the chosen old application code in a new main change, pass the gate, and publish a higher version/build. Sparkle then offers that corrected release normally. If the app cannot run its updater, a retained ZIP is also available for manual recovery. The existing isolated watchdog acceptance is historical evidence, not proof of production signed rollback yet.

## Secret custody and activation

Configured with Leo's approval on October 17:

- Repository secret `REPOHUB_SPARKLE_PRIVATE_KEY`: the Ed25519 private seed, never source-controlled or printed.
- Repository variable `REPOHUB_UPDATE_PUBLIC_KEY`: matching public verification key.
- `REPOHUB_RELEASE_ENABLED=false`: publishing stays disabled.
- Leo confirmed on October 17 that he saved the recovery key in his password manager. This is user-confirmed custody; the password-manager contents were not inspected. The owner-only local recovery file remains outside Git. Do not reproduce the seed in issues, logs, docs or chat.

After Apple membership activation, configure the following repository secrets without sharing credentials in chat:

| Secret | Purpose |
|---|---|
| `REPOHUB_CERTIFICATE_P12` | Base64-exported Developer ID Application certificate **and private key** |
| `REPOHUB_CERTIFICATE_PASSWORD` | Password protecting that P12 export |
| `REPOHUB_SIGNING_IDENTITY` | Exact `Developer ID Application:` signing identity |
| `REPOHUB_NOTARY_KEY` | App Store Connect team API private key in P8 text form |
| `REPOHUB_NOTARY_KEY_ID` | That API key's identifier |
| `REPOHUB_NOTARY_ISSUER` | That team key's issuer identifier |

Use a disposable runner keychain; restore its prior search list and remove the temporary keychain/secret files in cleanup. Never enable shell tracing or print subprocess signing arguments. An interrupted hosted runner is disposable; no signing material is uploaded as an artifact. Apple's response must explicitly be Accepted; stapler validation and Gatekeeper assessment still gate archive preparation. Developer ID signing includes hardened runtime and trusted timestamps.

Recovery custody is confirmed. Before enabling publication, configure Apple credentials, finish a first signed-package/notarization test and review the guarded first install from the old external-runtime/launchd layout. Then set `REPOHUB_RELEASE_ENABLED=true`. The workflow becomes automatic once present on main; it does not run directly from this feature branch. A failed release job can be rerun, retaining the exact main-source checks. New main changes naturally trigger a new Golden Gate and publication attempt.

## Current verification limits

A real unpublished GitHub draft probe confirmed exact-source targeting, uploaded/downloaded fixture-byte equality and complete probe cleanup. It exposed and corrected premature tag resolution: new draft tags do not exist until publication. Production app publication still awaits Apple signing.

Policy, publication-order/failure and secret-cleanup regressions run in the Golden Gate, along with pinned actionlint workflow validation. Simulated GitHub/signing cases prove the control flow, not Apple service acceptance or a live public release. No production release exists yet; the feed URL becomes live on the first successful signed publication. No installed Pro/Air app has been replaced by this work. Native permission continuity and the outstanding reliability matrix remain recorded separately. Apple activation is still user-reported pending.

Sources: [GitHub workflow-run security and semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run), [Sparkle update signing](https://sparkle-project.org/documentation/), [Apple notarization](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).

Signing checkpoint — October 17: local inspection found zero usable Developer ID Application identities. No notarization submission was made; production signing and Apple submission credentials remain required.
