# Dev, Testing and Stable updates

Implemented and branch-validated for roadmap step 1, October 20, 2026. The
unpublished GitHub Apple-signing validation also passed; see the
[exact-source record](RELEASE_DELIVERY.md#unpublished-signing-validation--october-20-2026).
No channel feed has been created, no update published and no installed Mac
changed by this work. Live publication and installed acceptance remain pending.

## Private experimental access — required, not implemented

Leo subsequently required Dev and Testing access only for his MacBook Pro and
MacBook Air. This supersedes the earlier plan to expose experimental packages
as public downloads with opt-in feeds. Both feeds and archives must require
authorization; hiding controls or obscuring URLs does not satisfy the requirement.
Stable remains public. Ordinary installations must offer only Stable, with
Dev/Testing enabled through explicit enrollment of Leo's two Macs.

The current branch still uses public GitHub experimental-feed URLs and accepts
channel selection without enrollment. It must not be activated for Dev/Testing
publication until private delivery is implemented and validated. Hosting and
credential-versus-hardware-bound enrollment remain a pending design decision;
no private repository, authentication service or device credential was created.
Per-Mac revocation and safe credential storage/redirect handling are required.
No client receives an Apple or Sparkle private signing key for downloading updates.

Acceptance must demonstrate rejected unauthorized/revoked feed and archive
requests, valid downloads on the two enrolled Macs, guarded UI/native selection,
no credential exposure in URLs/DOM/diagnostics or to unapproved redirect hosts,
and functioning public Stable updates. Promotion must publish the accepted
private Testing archive publicly with identical bytes and signature, without
including experimental-access credentials. Existing source/gate and installed
acceptance requirements still apply. This section records requested work; it
does not claim that the current publisher enforces it.

## What each channel means

| Channel | Required before delivery | Publication route |
| --- | --- | --- |
| Dev | Clean committed source, focused Dev receipt, native build, coordinated package checks and verified Sparkle signature | Local Pro command; no branch-based Actions validation |
| Testing | Full clean macOS Golden Gate and an exact successful Golden rules push run from this repository | Accepted main automation, or explicit promotion of a Dev package after its exact source passes the full gate |
| Stable | Testing requirements, protected-main source/tree checks, notarized Developer ID package, exact-package Pro/Air acceptance and explicit approval | Explicit promotion only; no rebuild |

The current implementation separates update offers but does not restrict access;
the private-delivery requirement above must be implemented before activation.
Normal installations currently default to Stable. Each Mac selects a channel in
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
- Channel diagnostics export only `stable`, `testing` or `dev` plus typed update
  reasons. An updater's ready state never establishes repository backup/upload
  success. Existing evidence without a channel remains readable.

## Local Dev command

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
