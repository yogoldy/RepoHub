# RepoHub update delivery

## Current staged policy — October 20, 2026

Leo approved Dev → Testing → Stable and explicitly approved local workflow edits
that route checked main builds to Testing and disable the former direct-Stable
command. The branch was subsequently pushed with explicit authorization for the
unpublished signing test below. It has not been merged to main. No live
repository variable, channel feed, published release or installed Mac was changed.

The complete operational contract is [Update channels](UPDATE_CHANNELS.md).

- **Dev:** build/publish locally on the Pro from clean committed source, after
  the fixed focused gate and native/package/signature checks. Push only the exact
  source tag for provenance; branch-based Actions validation is not required.
  This narrow exception cannot publish Stable or relax protected-main checks.
- **Testing:** full clean macOS Golden Gate and exact successful GitHub contract
  run. The existing main workflow retains checkout by triggering SHA, gate rerun,
  signing isolation and uploaded-byte verification, but targets a prerelease
  Testing feed. An existing Dev archive can also be promoted after full checks
  on its exact source. Missing/skipped/failed checks stop delivery.
- **Stable:** promote an existing Testing package only after explicit approval
  of its exact tag, recorded Pro/Air acceptance, current accepted protected main
  with matching source tree, and Developer ID signing/notarization. Promotion
  changes feed metadata, not archive bytes. No automatic main-to-Stable path
  remains in this source; the old `tools/publish_release.py` CLI fails closed.

Public latest remains the existing Stable URL. Dev and Testing use separate
prerelease feeds and never become latest. Leo subsequently required access only
for his Pro and Air: [private experimental delivery](UPDATE_CHANNELS.md#private-experimental-access--required-not-implemented)
must be implemented before activation. The current branch's public experimental
URLs and unauthenticated channel selection do not meet that requirement yet.
Channel changes are explicitly saved per
Mac and do not downgrade an already-installed newer build. Use the same signing
identity across channels when Apple credentials are configured in roadmap step 2.
Personal ad-hoc Dev/Testing is honestly marked; new Stable promotion rejects it.

Publishing and installation remain separate actions. This step authorizes local
implementation and validation only, not publication or installation. Keep
untested Apple services, real feeds, permissions and native UI behavior explicit.
The staged publisher temporarily performs no package pruning because the old
four-package rule could delete an archive still referenced by another channel.
No backup/archive data or unrelated release is deleted by this change.

## Unpublished signing validation — October 20, 2026

Leo authorized a branch-only push and manual signing test, without main merge,
release publication, feed changes or installation. Both the local clean macOS
gate and the [GitHub branch gate](https://github.com/yogoldy/RepoHub/actions/runs/39531738911)
passed on `49462f18482093ea380ccbaafe5a686db5d75ac7`. The local gate ran 334
Python tests with zero skips, all 26 registered rules and all 31 build/tool checks.

The [manual signing run](https://github.com/yogoldy/RepoHub/actions/runs/39531752665)
repeated the full gate, then successfully used the saved GitHub credentials to
decrypt/import the P12 in a disposable keychain, sign the coordinated Developer
ID app/helper, obtain Apple's Accepted notarization result, staple/validate the
ticket, pass Gatekeeper assessment, and prepare and independently authenticate
the Sparkle-signed archive. No credential values were recorded in source or the
bounded receipt. The job's failure-explanation step was intentionally skipped
because its prerequisite checks passed; it is not a skipped regression test.

The validation-only version `0.0.0`, build `1`, and non-release tag cannot pass the
managed release/promotion contract; no global release number was reserved.
Archive: 28,704,263 bytes, SHA-256
`57f66caa875a78a83af9df3985782238470c32b13dc814554612bf155f7f6c36`.
Its receipt records `result=passed`, unchanged source, `published=false` and
`installed=false`. Temporary package/archive/signing files were cleaned; the
bounded JSON remains in the Actions log and summary.

After the test, main remained `77ad73b6ebd5f52b2f92ce437abf59506827457a`, public
latest remained `repohub-v0.0.7-b7`, and `REPOHUB_RELEASE_MODE` remained
`personal_adhoc`. The existing main publisher has not yet received the branch's
Testing-only changes. The test does not enable Developer ID release mode or
claim live channel delivery, installed acceptance, permission continuity or Air
coverage. Those remain subsequent roadmap actions with their own authorization.

## Historical personal delivery record — October 17, 2026

The following records the earlier single-feed implementation and its credential
setup. Its automatic-publication, retention and pre-Apple Stable policy is
superseded by the staged policy above. Preserve its dated evidence limits; do
not treat the old release versions or Air state as a fresh observation.

Leo approved easy delivery to his own Macs: a protected main merge with a passing automated Golden Gate may publish an update; installed-Mac testing follows delivery. It is not a claim that every native interaction has been validated. Keep the outstanding native reliability matrix and signing/permission evidence visible. Do not add an unstated native approval prerequisite to personal delivery. This supersedes the earlier pre-delivery native acceptance requirement for this personal updater channel only; it does not authorize bypassing main protection, publishing failed checks or silently installing daily apps.

## Temporary personal channel — approved October 17

Leo explicitly approved delivery before Apple membership activation. Set
`REPOHUB_RELEASE_MODE=personal_adhoc`: use the existing production app identity,
HTTPS feed and Ed25519 archive key with local ad-hoc code signatures. This mode
requires no Apple certificate or notarization credential. It does not claim Apple
notarization or stable permission continuity. `developer_id` remains available and
requires all its original Apple checks; unknown modes fail closed.

Non-test packages enable Sparkle background discovery with its supported one-hour
minimum interval. Manual Check for Updates remains available at any time. Silent
download/installation and system profiling are disabled. Test identities keep
background network checks disabled. The Golden Gate verifies these values through
Sparkle's actual SPUUpdaterSettings API against a complete built app, not just the
Python dictionary. Scheduled checks produce a typed diagnostic reason.

The first Pro install retires the legacy helper launch agent, retains the previous
app/runtime/plists for rollback and keeps the existing config/data/schedules outside
the bundle. The app launch agent remains responsible for login startup; the bundled
app owns its helper. Air deployment is outside this change.

## Automatic path

`Golden rules` completes for a main push → `Publish signed update` checks the same source → packages the coordinated app → Sparkle archive signature verifies → upload draft → download and compare every asset → recheck current main → publish as latest → confirm latest → retain four managed release packages. In `developer_id` mode, Developer ID signing, accepted Apple notarization and ticket stapling must also pass before archive preparation. The approved `personal_adhoc` mode uses local ad-hoc code signatures and does not claim those Apple checks.

The release job is enabled through `REPOHUB_RELEASE_ENABLED=true` with `REPOHUB_RELEASE_MODE=personal_adhoc`, following the clean exact-main gate and actual package/signature validation. A fork, pull-request run, failure, stale main commit or missing `automated-contract` success is rejected. It checks out the triggering full SHA, not a moving branch, does not consume artifacts or caches from untrusted runs, and reruns the clean macOS gate before exposing signing secrets to the packaging step. The publishing job has contents-write/actions-read access; other jobs keep read-only access. Jobs serialize, and a newer main commit supersedes a still-packaging older candidate.

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
- Publishing was initially configured disabled. It is now enabled with `REPOHUB_RELEASE_ENABLED=true` and `REPOHUB_RELEASE_MODE=personal_adhoc`; the first actual publication succeeded.
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

Recovery custody is confirmed. For developer_id mode, configure Apple credentials and finish a first signed-package/notarization test before switching the release mode. Personal publishing is already enabled on main and does not require those Apple credentials. The workflow does not publish directly from feature branches. A failed release job can be rerun, retaining the exact main-source checks. New main changes naturally trigger a new Golden Gate and publication attempt.

## Current verification limits

A real unpublished GitHub draft probe confirmed exact-source targeting, uploaded/downloaded fixture-byte equality and complete probe cleanup. It exposed and corrected premature tag resolution: new draft tags do not exist until publication. Developer ID app publication still awaits Apple signing; the authorized personal channel does not.

Policy, publication-order/failure and secret-cleanup regressions run in the Golden Gate, along with pinned actionlint workflow validation. Simulated GitHub/signing cases prove the control flow; the first live personal publication additionally verified the actual GitHub delivery path. Apple service acceptance remains untested. The feed is live with 0.0.1; receipts identify personal ad-hoc versus Apple-signed distribution. The Pro completed its guarded transition to published 0.0.1; the Air remains unchanged. Native permission continuity and the outstanding reliability matrix remain recorded separately. Apple activation is still user-reported pending.

Sources: [GitHub workflow-run security and semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run), [Sparkle update signing](https://sparkle-project.org/documentation/), [Apple notarization](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).

Signing checkpoint — October 17: local inspection found zero usable Developer ID Application identities. No notarization submission was made; production signing and Apple submission credentials remain required.


## Pro bootstrap evidence — October 17

Protected PR #7 merged as 586511227918804206435d68f9396daf4444751c.
The automatic main gate and publication job succeeded, producing
[0.0.1 / build 1](https://github.com/yogoldy/RepoHub/releases/tag/repohub-v0.0.1-b1).
The downloaded archive's Ed25519 signature, SHA-256, release source, bundle resource
inventory and code signature verified before installation. Size: 28,569,211 bytes.
The real Sparkle settings API confirmed background discovery, one-hour checks,
user-controlled installation and disabled system profiling.

Two initial launch-agent handoffs returned bootstrap EIO and restored the previous
installation. The recorded protected config/registry/settings hashes remained equal,
and the original helper returned with 13 repos. Refreshing the bundle's Launch
Services registration before bootstrap then completed the transition. The accepted
private migration journal records source/build, matching helper, 13 repos and
protected_unchanged=true, retaining the prior app and launch plists for rollback.
The legacy external runtime remains untouched; its service agent is retired so the
packaged app owns the only helper. No personal migration installer or daily TCC reset
ran. Actual native menu evidence showed the new backup-location/schedule lines and
conservative scanning states during the initial check.

The follow-up installer fix provides a real release to exercise GitHub-to-Sparkle
replacement on this installed Pro. Keep its resulting native/diagnostic preservation
receipts private. This does not close the older comprehensive native reliability
matrix or prove future Apple permission continuity.
