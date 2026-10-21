# Dev, Testing and Stable updates

Implemented and branch-validated for roadmap step 1, October 20, 2026. The
unpublished GitHub Apple-signing validation also passed; see the
[exact-source record](RELEASE_DELIVERY.md#unpublished-signing-validation--october-20-2026).
No channel feed has been created, no update published and no installed Mac
changed by this work. Live publication and installed acceptance remain pending.

## Experimental offers and open-source distribution

Leo clarified that ordinary users must not be offered experimental updates, but
source and experimental packages may remain public. This supersedes the brief
private-download proposal: no private repository, authentication service,
hardware allowlist or download credentials are required or were provisioned.
Deliberate advanced access to a public experimental package is acceptable.

Ordinary installations follow Stable, with experimental controls kept out of
the normal settings flow. Dev/Testing participation is deliberately enabled
locally on Leo's Pro and Air. This is a local testing preference, not an access
control or a promise to prevent other people from downloading public packages.
No client receives an Apple or Sparkle private signing key to download updates.

Ordinary installations show Stable update guidance and Check for Updates, without
a channel selector or channel Save/Cancel controls. The native updater also forces
Stable and rejects experimental saves unless a deliberate local Boolean opt-in
was present when the process started. An old saved Dev/Testing selection alone
does not enable experimental offers. Missing or malformed native policy replies
keep the page's selector hidden, show settings as unavailable, and disable saving
and the page's update action until a valid reply loads. Shared action-row CSS
explicitly honors the hidden state for these controls.

### Enable experimental channels on a test Mac

Quit RepoHub, then run in that Mac's Terminal:

```sh
defaults write com.leogoldberg.repohub experimentalUpdateChannelsEnabled -bool true
```

Reopen the channel-capable app. Settings → App updates now shows Stable, Testing
and Dev, with explicit Save changes. Enabling the controls alone keeps the saved
channel (Stable for a new preference); it does not install or publish anything.
This command can be used deliberately by others too; it is not machine authentication.

To return to ordinary Stable offers, quit RepoHub and run:

```sh
defaults delete com.leogoldberg.repohub experimentalUpdateChannelsEnabled
```

Reopen the app. The effective channel is now Stable even if Dev/Testing was saved.
The saved preference is retained, so re-enabling experimental channels later
restores that selection. Neither operation downgrades the installed app, changes
backup settings or removes archives. Both commands affect only this Mac; they
are not applied to the Pro or Air by the implementation tests. The opt-in is
read once per launch so external changes cannot switch policy halfway through
an update session. Test bundles use their own preference domain and fixture feed.

Tests exercise Stable defaults, strict Boolean enablement, persisted preferences
in another process, opt-out with an existing Dev selection, guarded channel
requests, exact offered channels and bounded diagnostic agreement. Existing
update/backup busy guards, no-downgrade behavior, full Testing checks and
exact-archive Stable promotion remain. Native installed acceptance is pending.

## What each channel means

| Channel | Required before delivery | Publication route |
| --- | --- | --- |
| Dev | Clean committed source, focused Dev receipt, native build, coordinated package checks and verified Sparkle signature | Local Pro command; no branch-based Actions validation |
| Testing | Full clean macOS Golden Gate and an exact successful Golden rules push run from this repository | Accepted main automation, or explicit promotion of a Dev package after its exact source passes the full gate |
| Stable | Testing requirements, protected-main source/tree checks, notarized Developer ID package, exact-package Pro/Air acceptance and explicit approval | Explicit promotion only; no rebuild |

The channels separate update offers; publicly hosted downloads are not restricted.
Normal installations offer Stable only. A deliberately enabled test Mac selects a channel in
Settings → App updates and uses Save changes. Selection changes no backup rules,
sources, schedules or permissions. Save is rejected during an update session or
when the matching helper cannot confirm backups are idle. Draft changes,
Cancel/Back and failed/conflicting saves do not silently select a channel.

Each channel is exclusive. Dev clients do not automatically fall back to Testing
or Stable; explicitly select the desired channel. Sparkle never downgrades a
newer installed build when switching to an older channel. The Mac waits until
that channel offers a newer build. Settings explain this limitation. Test bundles
retain their isolated fixture feed and disabled background discovery.

## Feed isolation and provenance

- Stable retains `releases/latest/download/appcast.xml`, preserving existing
  clients. Dev and Testing use fixed prerelease feed tags
  `repohub-channel-dev` and `repohub-channel-testing` under the same repository.
- Experimental release creation/publication explicitly uses `--latest=false`
  and prerelease status. Only explicit Stable promotion can move public latest.
- Each feed contains one item. Dev/Testing items have the matching Sparkle
  channel tag; Stable omits it. The native updater checks the item against the
  selected channel before download, in addition to Sparkle's channel filtering.
  JavaScript cannot supply a URL, command or archive path to select a feed.
- Every candidate has an immutable source/build/archive receipt and origin
  `channel-proof.json`. Current stage proof is embedded in its appcast, so stage
  and evidence are replaced together as one asset. It records the exact gate run;
  Stable also records the acceptance receipt digest. Public proofs contain no
  local paths or raw test logs. Stage metadata can change; archive bytes cannot.
- Channel diagnostics export only `stable`, `testing` or `dev`, the launch-time
  `experimental_channels` value (`enabled`/`disabled`), and typed update reasons.
  Disabled policy paired with an experimental effective channel is rejected.
  An updater's ready state never establishes repository backup/upload success.
  Existing evidence without these optional fields remains readable.

## Local Dev command

### First signed Dev handoff

Before the first local publication, prepare the existing release environment on
the Pro with Developer ID mode, the original Sparkle key and its matching public
key, the certificate export/password, and the notarization API credentials listed
in [release delivery](RELEASE_DELIVERY.md). A local code-signing identity alone
does not satisfy the publisher's disposable-keychain credential contract. Stored
GitHub secret values cannot be downloaded to populate a local environment.
Do not paste private keys or passwords into chat or shell command history; supply
them through a user-controlled secure local session. Do not rotate the Sparkle
key merely because local publication has not yet been configured.

The October 20 preparation confirmed a valid local Developer ID signing identity
and the presence of the previously exported certificate/API-key files without
opening them. Leo confirmed that the original Sparkle key is available locally.
The local release environment is not populated, so its secret imports and a real
signed Dev package remain unverified. No experimental feed, publication,
installation or opt-in on either daily Mac is implied by the implementation.

Once credentials and publication are authorized, rerun the focused clean-source
gate immediately before publication; a prior receipt is not a standing approval
and the publisher requires a fresh receipt. Verify the resulting Dev feed and
downloaded archive before the Pro's controlled bootstrap installation. Its older
installed app cannot select Dev yet. Keep that installation, permission continuity
and subsequent updater acceptance separate from the local gate.

### Focused validation and publication

Run from the canonical RepoHub checkout after committing the intended change:

```sh
python3 tools/dev_gate.py --output /new/private/path/dev-gate.json
```

The fixed focused suite covers backup/persistence/request guards, setup and the
channel system, plus all shipped JavaScript syntax and a native app build.
Missing modules, skipped/expected-failure tests, changed source or compilation
failure stop the gate. Add change-specific tests to the fixed suite when the
changed boundary needs them; this receipt is deliberately not a full Golden Gate.
Packaging subsequently compiles against pinned Sparkle and verifies resources,
code signatures and archive signatures before publication.

For a separately authorized Dev publication:

```sh
python3 tools/channel_release.py dev --publish --gate-receipt /private/path/dev-gate.json
```

Publication additionally requires `REPOHUB_RELEASE_ENABLED=true`, the public
update key and explicit signing material in the existing release environment.
It never searches private files or installs credentials. No secret belongs in
shell history, source control, issue bodies or diagnostic exports. Developer ID
credential setup remains roadmap step 2. The temporary personal ad-hoc mode may
publish Dev/Testing with honest metadata; new Stable promotion rejects it.

The command validates the canonical origin and pushes an exact
`repohub-source-<full SHA>` tag, not a branch. This makes source available to
GitHub Releases without starting the branch-based Golden rules workflow. It is
still a remote write and requires publication authorization. A branch push later
continues to run its normal protected checks.

## Testing and Stable promotion

### Unpublished Apple-signing validation

Before the first signed delivery, manually run the existing **Golden rules**
workflow on the reviewed branch with `validate_signing=true`. This is separate
from Dev/Testing publication. The default is false; ordinary pushes and pull
requests do not load Apple or Sparkle secrets into this step.

The complete clean macOS gate runs first. `tools/validate_signing.py` then checks
its exact source/digest, imports the certificate export in a disposable keychain,
and uses the existing Developer ID packaging/notarization path. Stapler,
Gatekeeper, resource hashes, the Sparkle key match/signature, and an independent
public-key archive verifier must pass. The workflow has only contents-read
permission and no publishing token. A validation-only version/tag cannot satisfy
the managed-release promotion contract. It creates no release, source tag, feed,
installation or GitHub package artifact. Temporary app/archive/key material is
cleaned; only bounded JSON evidence is printed in the job and its summary.

After separately authorized branch publication, invoke it with
`gh workflow run golden-rules.yml --ref <reviewed-branch> -f validate_signing=true`.
The existing workflow file is already registered on main; the reviewed branch
provides the opt-in input and validation implementation. Its full gate still
runs for ordinary pushes/PRs without signing secrets. The job timeout allows the
additional Apple submission wait; automatic release triggers are unchanged.

The test does not change the repository's release mode. A failed prerequisite or
signing step is not delivery evidence. Installed channel behavior and permission
continuity still require the separate Pro/Air acceptance sequence.

The intended main workflow retains checkout by triggering SHA, a complete clean
gate rerun and the existing signing/notarization checks. Its publication command
is `tools/channel_release.py testing --publish`, with the exact run ID and gate
receipt. Automatic main publication targets Testing, never Stable.

An existing Dev candidate can instead be promoted with `operation=promote`, its
managed `--tag`, `--to testing`, the exact successful push `--run-id` and matching
full `--gate-receipt`. Forks, pull-request runs, missing/duplicate/skipped contract
jobs and stale or mismatched receipts are rejected.

Stable uses the same promotion command with `--to stable`, an exact current-main
gate/run, `--approve-stable <exact candidate tag>` and `--acceptance <private JSON>`.
The accepted candidate source must be an ancestor of protected main and have the
same Git tree. Main movement to a different tree requires a new candidate rather
than publishing an older package silently. Stable cannot regress the build.

The private acceptance JSON has schema 1 and the candidate's exact
`source_revision`, string `build`, `archive_sha256` and `hosts`. Both `pro` and
`air` must explicitly mark `permissions`, `configuration`, `install_update`,
`backup` and `channels` as `passed`; Air additionally requires `onboarding`.
These are operator attestations supported by recorded native observations, not
facts inferred from CI. Never create a passing receipt merely to unblock a
command. Pending/failed checks cannot be promoted. Manual installation prompts
and unavailable machines stay pending.

Promotion downloads and hashes the candidate, verifies its signature with the
configured public key, then modifies only the appcast with its embedded proof. It never builds,
resigns or uploads a different archive. Uploaded bytes are downloaded and compared
before the channel pointer changes. Stable's original archive URL continues to
identify the same package accepted in Testing.

## Concurrency, interruptions and retention

A repository-wide annotated Git tag lock serializes local and hosted publishers.
Its unique owner object is checked before mutations and before removing the lock.
A conflicting lock fails closed. Draft releases reserve globally increasing build
numbers across all channels, so failed builds cannot overwrite a later candidate.

An interrupted process may leave its lock, draft or metadata update. Inspect the
owner, active jobs/process and release/feed state before deliberate recovery;
never remove a lock just because it looks old. No automatic stale-lock stealing
is implemented. A promotion interrupted after metadata publication can be retried
with `--resume`; the command rechecks gates, approval and acceptance. Existing
matching feed bytes are idempotent; older or same-build different feeds are refused.

Read-only inspection on October 20 found repository immutable releases disabled
and the existing 0.0.7 release mutable. Local publishers repeat the administrative
repository check before release/lock writes. Hosted publishing retains its narrow
contents/actions token: it checks published release/pointer metadata instead,
then checks the new candidate is still a mutable prerelease before exposing a
feed. If repository immutability changes during a run, publication can leave an
unreferenced prerelease, but cannot silently move Stable or report successful
channel delivery. No setting is disabled and no admin credential is added to CI.
Live feed creation still requires acceptance.

GitHub asset replacement is not atomic. Replacing a prerelease pointer can briefly
make that experimental feed unavailable. Failure stops confirmation and is not
reported as successful delivery; it does not select another channel or modify
Stable. Immutable GitHub releases reject metadata updates and require a deliberate
distribution redesign; the publisher never disables repository immutability.

The new publisher performs no automatic release deletion. The old flat retention
policy cannot safely delete packages referenced by three feeds. Channel-aware
retention is deferred; existing archives, unrelated releases, source tags and
local recovery copies are not removed by this implementation.

## Checks and remaining acceptance

GR26 registers channel/UI/diagnostic contracts, exact-run checks, publication
ordering, public-key verification, lock ownership, interrupted promotion and
unchanged-archive promotion. The existing Golden rules workflow discovers these
tests through the full gate. Tests simulate GitHub mutations and use synthetic
archives/public RFC signature material; they never publish fixtures.

The branch gate and unpublished GitHub Developer ID/notarization test passed on
the source recorded above. Live feed creation, hosted promotion/mutable-release
behavior and actual channel/update behavior on Pro/Air still require separately
authorized delivery. Signed-package validation does not establish installed-Mac
permission continuity or native acceptance.

References: [Sparkle channels and feeds](https://sparkle-project.org/documentation/publishing/),
[updater cycle reset](https://sparkle-project.org/documentation/programmatic-setup/),
[GitHub release semantics](https://docs.github.com/en/rest/releases/releases).
