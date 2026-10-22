# Local Dev publishing

This developer-only workflow replaces the October 22 temporary handoff scripts.
It does not change the app's backup rules, reset macOS permissions, install an
update, promote Testing/Stable or configure the Air.

## One-time provisioning

`tools/local_dev.py setup --profile /private/setup-profile.json` runs in the
owner's Terminal on the Pro. The profile is a private, owner-only JSON file:

```json
{
  "certificate_path": "/absolute/path/to/Certificates.p12",
  "notary_key_path": "/absolute/path/to/AuthKey_KEYID.p8",
  "signing_identity": "Developer ID Application: Your Name (LJM5FKB7DY)",
  "notary_key_id": "YOURKEYID1",
  "notary_issuer": "00000000-0000-0000-0000-000000000000",
  "update_public_key": "existing public Sparkle key from repository configuration"
}
```

The profile, certificate and API-key files must be regular, owner-only files
with no symlinks or hard links. Use the existing files and keys; do not generate
replacement keys to make setup pass. The profile contains metadata/paths only,
never a password or private signing key.

Setup compiles a separate helper outside the repository and signs it with the
existing Developer ID identity. Both the wrapper and helper verify that code
identity before accessing Keychain. Setup then requests the original Sparkle
private key and certificate-export password through hidden input. It verifies
the original public key against GitHub's configured public key, private/public
key continuity, certificate import and Apple authentication before saving.

The bundle includes the existing certificate export, its password, notarization
API key and original Sparkle key, plus their public metadata. It is stored as one
generic-password item in the Mac's
default user Keychain, service `com.leogoldberg.repohub.dev-publisher`, account
`release-credentials-v1`. Its ACL trusts the signed helper, not all applications.
There is no unattended overwrite/rotation command. An existing item stops setup
before another secret prompt. Wrong input or failed preflight stores nothing,
so the same setup command can be retried without a replacement launcher.

The helper and non-secret metadata live in the owner-only
`~/Library/Application Support/RepoHub Developer/` directory. The original key
files are not deleted or added to Git. Developer tooling and credentials are
excluded from the app's explicit package lists. Installed users never need
publisher signing credentials to receive an update.

## Each authorized Dev publication

From any directory, invoke the canonical checkout's script:

```sh
python3 /absolute/path/to/RepoHub/tools/local_dev.py publish --publish
```

This is an explicit remote-write command, not a background publisher. It:

1. Requires local ARM64 macOS, clean committed source and a trusted helper.
2. Runs the fixed focused Dev gate without signing credentials in its environment.
3. Rechecks the exact source and receipt before loading credentials from Keychain.
4. Revalidates signing-key continuity, certificate import and Apple authentication.
5. Invokes the existing staged Dev publisher in Developer ID mode. Its source
   tag, lock, build reservation, package/notarization/signature checks and Stable
   isolation still apply. It never invokes a Stable promotion or installer.

There are no per-release pasted-secret prompts. A locked Keychain, denied access
or cancelled system authorization stops the run; macOS authorization/unlock
prompts may still occur. Do not promise silent access across every system state.
`status` reports only whether credentials are configured, not their values.
Run metadata and credential-free gate logs are private under the developer
directory's `runs/`. Signing subprocess output is captured and discarded rather
than persisted or echoed. Credential values are never command-line arguments
to this wrapper/helper or printed into its status output.

## Permission continuity is a separate acceptance result

Build 9 moved the Pro from ad-hoc signing to Developer ID and needed renewed
Desktop consent. It is not evidence of a signed-to-signed permission regression.
Packaging and archive preparation now enforce build 9's Team ID and designated
requirements for the app, Python interpreter and cloud helper. A foreign team,
renamed helper or hash-bound requirement fails before delivery. These checks do
not read or edit the TCC database and do not establish that permission persisted.

After provisioning, authorize a new Dev delivery and install it through Sparkle
on the Pro. Record exact old/new app/helper identities, protected configuration
hashes, whether macOS asked again, helper-observed source reads and the actual
backup result. A reset/regrant cannot count as retained permission. Leave Air,
Testing and Stable acceptance pending until exercised separately.

## Verification limits

Automated tests use synthetic credentials and an isolated temporary Keychain.
They test duplicate refusal, locked reads, complete/bounded pipe input, unsigned
helper refusal, secret-free logs/errors, fresh retries, source/gate failure and
Dev-only dispatch. They do not read real secrets, publish a package, install an
update or reset daily permissions. The full Golden Gate discovers these tests;
the focused Dev suite includes the local-publisher and signing-identity modules.
Existing GitHub triggers remain unchanged.
