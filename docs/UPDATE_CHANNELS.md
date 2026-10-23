# Dev and Stable updates

## Current policy — October 22, 2026

Leo replaced Dev → Testing → Stable with **Dev and Stable**. Testing is retired.
Validation is recorded on each exact candidate, in this order:

| Candidate evidence | Meaning |
| --- | --- |
| Local checks passed | Clean-source focused tests, native build and signed-package checks allow Dev publication |
| GitHub checks passed | The complete clean macOS gate and exact successful canonical push run qualify the same Dev archive |
| Installed acceptance passed and approved | Recorded Pro/Air use cases and explicit exact-tag approval allow Stable promotion |

A validation stage is not another update channel. GitHub qualification leaves
an update on Dev; ordinary users continue receiving Stable only. Qualification
and promotion change appcast/proof metadata, never rebuild, resign or replace
archive bytes. The package checksum, source revision and build identify the
candidate through every stage. An installed app needs a new version to remove
Testing from its selector; existing packages need no rebuild to qualify/promote.

The local implementation does not publish, install or promote anything by
itself. Build 10's live release remains as previously published until separately
authorized qualification. Its Pro update/permission result is recorded below.

## Ordinary-user offers and saved preferences

Stable remains the default. Only a deliberate Boolean local preference enables
Dev selection on Leo's Pro/Air; public experimental downloads are acceptable.
No private hosting, device authentication or download credentials are required.
Never ship Apple or Sparkle private keys. Native bridge requests retain the exact
page/window/request-ID, revision and backup/update busy checks. Malformed policy
replies disable saving and the page's update action. Shared hidden selectors
keep experimental controls out of ordinary settings.

Enable experimental offers deliberately while RepoHub is quit:

```sh
defaults write com.leogoldberg.repohub experimentalUpdateChannelsEnabled -bool true
```

Reopen, select Dev in Settings → App updates and save. Removing the opt-in and
restarting forces Stable without deleting the saved preference. A retired saved
Testing selection falls back to Stable without rewriting preferences; a new
Testing save, feed or diagnostic channel is rejected. Test cases use isolated
preference domains. Switching channels never downgrades an installed build.

Dev uses `releases/download/repohub-channel-dev/appcast.xml`; Stable keeps
`releases/latest/download/appcast.xml`. Dev release/pointer metadata is always
prerelease and never public latest. The native updater accepts only the selected
channel, in addition to Sparkle filtering. Backup readiness remains separate.

## Local Dev publication

Use the provisioned [Keychain workflow](LOCAL_DEV_PUBLISHING.md):

```sh
python3 tools/local_dev.py publish --publish
```

The wrapper requires explicit publication authorization, clean committed local
ARM64 macOS source and a fresh focused gate before loading credentials. It signs,
notarizes and verifies the package, reserves a global build under the publisher
lock, uploads/downloads and compares assets, then updates only Dev. It never
runs the branch-based GitHub gate or installs an app. A locked Keychain can still
require macOS authorization; routine publication needs no pasted signing secrets.

## GitHub qualification without rebuilding

```sh
python3 tools/channel_release.py qualify --tag <candidate-tag> --publish \
  --run-id <exact-successful-push-run> --gate-receipt /private/full-gate.json
```

Run from clean source matching the candidate and its full receipt. Qualification
needs the configured public Sparkle key and authorized GitHub writes, not private
Apple/Sparkle signing keys. It independently authenticates the downloaded archive
and verifies exact source/build/hash. The successful Golden rules push must be
from this repository's main or codex branch, not a PR/fork run; the unique completed
`automated-contract` job and all referenced local regressions/builds must pass.
Missing, skipped, failed or stale evidence stops before metadata mutation.

`publish-update.yml` keeps the existing successful Golden rules workflow-run
trigger and adds canonical codex branches alongside main so a Dev source can be
qualified before merging creates a different SHA. It checks out that triggering
SHA and reruns the complete clean gate. `qualify --auto` finds the newest published
candidate for that exact source; no match is reported honestly without creating
a package. CI loads no private signing secrets and cannot promote Stable.

The embedded public appcast proof and release notes show `local_checks`,
`github_checks` and `installed_acceptance`, each passed/pending. GitHub qualification
records the exact run ID while installed acceptance stays pending. The original
release receipt and origin proof remain unchanged, as do archive bytes/signature.
Refreshing qualification for the current Dev build is allowed only for the same
source/build/hash/archive URL. Qualifying an older candidate cannot replace a
newer Dev offer. The publisher downloads and confirms metadata before the pointer
moves; public latest must remain unchanged.

Older Dev packages, including build 10, remain readable without the new validation
fields. They cannot go directly to Stable: fresh exact-source qualification must
record the full gate and successful GitHub run first. No old result is silently
marked passed. Qualification's full local gate also establishes the local checks
for a legacy candidate whose original proof lacks explicit stage fields.

## Explicit Stable promotion

```sh
python3 tools/channel_release.py promote --tag <candidate-tag> --to stable \
  --run-id <current-main-successful-push-run> --gate-receipt /private/main-gate.json \
  --acceptance /private/native-acceptance.json --approve-stable <candidate-tag> --publish
```

Stable requires the recorded exact-candidate GitHub qualification, a current full
protected-main gate, candidate ancestry and identical Git tree, notarized Developer
ID signing, and explicit approval of the exact tag. The private schema-1 acceptance
record must match source/build/archive hash. Both `pro` and `air` must pass
`permissions`, `configuration`, `install_update`, `backup` and `channels`; Air
also requires `onboarding`. Never create passing attestations to unblock a command.

Promotion rechecks the GitHub qualification and current main, authenticates the
archive and retains its original download URL/bytes. Only feed/proof metadata and
release visibility change. Stable proof records all three passed stages and the
acceptance digest. No automatic Stable publishing or downgrade is permitted.
An interrupted promotion requires explicit `--resume` and all evidence again.

## Concurrency, recovery and verification limits

The repository-wide publisher tag lock remains exclusive and owner checked.
Failed drafts reserve build numbers. Inspect a leftover lock, jobs and remote
release/feed state before deliberate recovery; never steal or delete an unrelated
lock or retry a remote timeout blindly. Pointer replacement is not atomic and may
briefly make Dev unavailable. Failures cannot silently switch to Stable. No
release retention deletion, permission reset or daily configuration change is
part of this implementation.

GR26 covers removed-channel rejection, controller/native/diagnostic agreement,
qualification without an archive upload/build, wrong-source/skipped/forged checks,
monotonic pointer refresh, explicit approval, Pro/Air acceptance, protected main,
archive authentication and interrupted promotion. Fixtures use synthetic data;
live qualification and Stable promotion remain pending. Installed backup/upload
and Air acceptance are separate from automated test results.

The original unpublished signing check remains documented in
[release delivery](RELEASE_DELIVERY.md#unpublished-signing-validation--october-20-2026).

## Local implementation validation — October 22, 2026

Implementation `94c0cf07ce06c6ab26dc5edb20cda81eb8d670e2` passed the complete
clean-source macOS Golden Gate: 355 tests, zero skips, all 26 registered rules and
31 command checks, including native/package builds and workflow syntax. Source
remained unchanged. The sandboxed native preference regression initially could
not synchronize its isolated domain; the host-access repeat and complete gate
passed without weakening assertions. These are local results, not a GitHub run.
No branch push, qualification, feed change, Stable promotion or installation was
performed. The installed Pro remains build 10 on Dev. Live two-channel delivery
and installed selector changes await a separately authorized update.

## Prior delivery and installed evidence

These dated checkpoints describe the earlier three-channel implementation and
actual Dev deliveries. The two-channel policy above supersedes their pending
Testing-stage instructions, preserving their exact observed results.

## Live Dev checkpoint — October 22, 2026

- Published [0.0.9 / build 9](https://github.com/yogoldy/RepoHub/releases/tag/repohub-v0.0.9-b9)
  from `a9b3895f36a4c76ac68882863baf1ffae26a4d43`; the Dev feed is live.
  Stable/public latest remains `repohub-v0.0.7-b7`. Failed draft build 8 remains
  reserved and unpublished with no assets; its draft-lookup regression is in GR26.
- The fresh focused gate passed 77 tests with zero skips and a native build on
  unchanged clean source. The first sandboxed gate could not synchronize isolated
  macOS test preferences; the native regression and complete gate passed with
  the required host access, without weakening their assertions.
- The downloaded 28,703,225-byte archive has SHA-256
  `a80d1f046769ac5144b940295fd204edd361b0f3d097dda4ad65a5d93079e1e1`.
  Its receipt/source, independent Sparkle signature, strict code signature,
  Gatekeeper notarized Developer ID assessment and stapled ticket verified.
- At this bootstrap checkpoint, the Pro ran that exact app/helper build. The
  previous app is preserved locally for rollback; all six protected configuration-file hashes match their
  pre-install snapshot. No source selection, backup destination, schedule or
  existing archive was changed by installation. The Air was not changed.
- macOS requested Desktop consent when moving from the old ad-hoc identity
  (code-hash requirement, no Team ID) to Developer ID (Team `LJM5FKB7DY`, unchanged
  bundle identifier). Leo reported Allow. The helper listed all 15 sources without
  permission errors; this is not complete content-verification or upload evidence.
  Permission continuity must still be tested with a subsequent signed update.
- The Pro's deliberate experimental opt-in is enabled. Initially the effective
  channel remained Stable. After the explicit Settings save, native evidence
  reports `experimental_channels=enabled`, `update_channel=dev`, `no_update`.
  Computer Use lost the transient panel before its click; no direct preference
  write bypassed the channel save. A subsequent installed update remains pending.
- The temporary publishing launcher needed hidden inputs and did not provision
  persistent credentials. Secure one-time Keychain provisioning and a repeatable
  local publishing command were the next priority before another Dev publication.
  Preserve explicit publication authorization, exact-source checks and Stable
  isolation; downloading/installing updates must never need signing secrets.

The repeatable [local Dev publishing workflow](LOCAL_DEV_PUBLISHING.md) is now
implemented locally with a signed Keychain helper and synthetic/disposable-
Keychain coverage. Leo completed real provisioning, and two retrieval/signing/
Apple-authentication preflights passed without pasted-secret prompts. The full
clean macOS gate passed on corrected code `e633268` (353 tests, zero skips).
Provisioning itself published and installed nothing and did not reset daily
permissions. The subsequent authorized publication is recorded below.

### Routine Keychain Dev publication — build 10

- Published [0.1.0 / build 10](https://github.com/yogoldy/RepoHub/releases/tag/repohub-v0.1.0-b10)
  from `6710337166496913814ddad4a887afa39829620b` on October 22 using stored
  Keychain credentials, without pasted keys or passwords. Its fresh focused gate
  passed 92 tests with zero skips, a native build and unchanged source.
- Downloaded all four public assets and verified the receipt/source, Dev stage,
  archive size/hash, independent Sparkle signature and exact pointer appcast.
  The 28,703,227-byte archive has SHA-256
  `29de397cf113d6194cec98b583415425705e296bb64ebce6e9f75b6aadc351dd`.
- The extracted app passed strict code-signature verification, Gatekeeper's
  notarized Developer ID assessment and stapled-ticket validation. App, Python
  helper and cloud-helper designated requirements match installed build 9.
- Stable/public latest remains `repohub-v0.0.7-b7`. No main merge, Testing/Stable
  promotion or Air change occurred. At publication, installation was left to Leo
  and remained pending. The private pre-update baseline records installed
  version/identities, six configuration hashes and native preferences. The later
  installed result is recorded below.

### Pro signed-to-signed update acceptance — October 22, 2026

Leo installed build 10 manually through Sparkle and reported “permissions
stable.” This passes Desktop permission continuity for the Pro's Developer-ID-
signed build 9 → 10 update. No daily permission reset or regrant was performed.

Read-only checks independently confirmed installed version 0.1.0/build 10,
matching helper build/source `6710337166496913814ddad4a887afa39829620b`, a valid
strict installed code signature, and unchanged app/Python/cloud designated
requirements. All six protected configuration hashes and the three checked
native preferences match the pre-update baseline; Dev remains selected and all
15 configured sources are listed. Private post-update evidence was saved.

This completes the immediate Pro update and permission-retention check, alongside
routine publication without pasted credentials. A new archive's verification or
confirmed cloud upload, broader failure/recovery cases, Air acceptance and
Testing/Stable promotion are not established by this checkpoint.
