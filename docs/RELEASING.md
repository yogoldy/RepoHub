# Releasing RepoHub

This describes how maintainers build, test and publish RepoHub. You don't need it to use or contribute to the app. The key rule: **publishing a build never installs it on anyone's Mac, and promoting a build never rebuilds it.** Users install updates themselves through Sparkle.

## The first public release

Build 14 maps to version 0.1.4. Confirm the imported ZIP, signature and appcast against the private archive and public release receipts before relying on their identity, to preserve update-feed continuity and build numbering. Later builds follow the steps below.

## Where to release from

Run every release command from a fresh clone of this repository. The publisher pushes tags from the checked-out commit, so an older checkout with a different history must never be used. Releases must stay editable (the repository's immutable-releases setting must be off), because the Dev feed pointer and release metadata are replaced in place.

## What a release is

A release is one ARM64 macOS app bundle, zipped, that contains everything the app needs:

- the native menu-bar app and the Sparkle updater framework,
- a pinned standalone Python (downloaded by SHA-256) and the helper modules,
- the iCloud status helper and the web interface,
- an immutable manifest of source revision, version, build number and component hashes.

The publisher staples the notarization ticket after building the production app. Qualification and promotion preserve the resulting ZIP bytes. Before starting the helper, the app checks bundle and manifest identity and verifies the listed resource files and symlinks against the contents of `Contents/Resources`. Settings, the workspace registry, schedules, credentials and backups live outside the bundle (app data in Application Support, backups in the chosen iCloud folder, native preferences in macOS defaults, and reporting credentials in Keychain), so replacing the app never touches them.

Versions follow the build number (build 14 is 0.1.4). Tags are `repohub-v<version>-b<build>` and point at the exact source that was built (except the imported first release, whose historical tag target and original source revision require comparison with the imported release receipt). A build number is never reused, even when a draft fails.

## Channels

- **Stable** is the default. Its feed is `releases/latest/download/appcast.xml`.
- **Dev** is for testing. Its feed is `releases/download/repohub-channel-dev/appcast.xml`, it is always a pre-release, and it never moves the public "latest".

Ordinary users follow Stable. A tester turns on Dev deliberately (quit the app, run `defaults write com.leogoldberg.repohub experimentalUpdateChannelsEnabled -bool true`, reopen, then pick Dev in Settings → App updates). Choosing a channel never downgrades an installed build. A channel is only an update feed; it doesn't change what "backed up" means.

## Checks a candidate passes

Evidence is recorded on the exact candidate (same source, build and archive hash), in this order:

| Stage | Meaning |
| --- | --- |
| Local checks | The focused gate (`python3 tools/dev_gate.py --output "$GATE_RECEIPT"` with `GATE_RECEIPT` set to a new receipt path), a native build, and signature and notarization checks passed. This allows Dev publication. |
| GitHub checks | The complete clean-source gate (`python3 tools/release_gate.py --require-clean`) and a successful GitHub Actions run on the same source qualify the Dev build. It stays on Dev. |
| Installed acceptance | Stable promotion requires installed-build checks for host labels `pro` and `air` and explicit approval of the exact tag. The tooling also supports a per-tag exception requiring explicit approval and all checks for `pro`. The public release notes record the exception and identify the waived checks for `air`. |

The tooling currently expects two acceptance hosts labeled `pro` and `air` (see the roadmap item on making this configurable). Qualification updates the appcast proof and Dev feed. Stable promotion also changes the GitHub release title, notes, prerelease status and latest designation. The archive bytes and signature never change.

## Steps

1. **Build.** `python3 tools/package_app.py --help` describes the bundle builder. It requires clean committed source on Apple silicon, pins every download by SHA-256, and never installs anything or registers a login item. Production builds are signed with a Developer ID identity.
2. **Prepare the update archive.** `python3 tools/update_feed.py --help` describes archive and appcast preparation. The archive is signed with the project's Ed25519 key; the matching public key is stored in the signed app’s `Contents/Info.plist` as `SUPublicEDKey`. The tool checks the two match, requires a stapled notarization ticket for production, and writes local artifacts and a hash receipt. It never publishes.
3. **Publish to Dev** from a Mac with the release signing credentials in Keychain: `python3 tools/local_dev.py publish --publish`. It needs explicit authorization, clean committed source and a fresh focused gate. It acquires the repository-wide publisher lock and reserves the build before signing, notarizing and verifying the package, then uploads, downloads and compares every asset, and updates only the Dev feed.
4. **Qualify with GitHub.** This needs the repository variable `REPOHUB_RELEASE_ENABLED=true`, and the same variable set in the shell that runs the command (promotion needs it too), together with `REPOHUB_UPDATE_PUBLIC_KEY` set to the project's public update key, which the verifier reads from the environment. After a successful GitHub Actions run on the same source: `python3 tools/channel_release.py qualify --tag "$TAG" --publish --run-id "$RUN_ID" --gate-receipt "$GATE_RECEIPT"`. It needs only the public Sparkle key and GitHub write access, never a private signing key. The automatic run for a merge to `main` finishes with `no_matching_dev_candidate` if it completes before the Dev build is uploaded. After uploading, rerun that original push run, or qualify manually with its run ID and the matching gate receipt. A fresh manual dispatch does not satisfy the push-event check.
5. **Promote to Stable.** `python3 tools/channel_release.py promote --tag "$TAG" --to stable --run-id "$RUN_ID" --gate-receipt "$GATE_RECEIPT" --acceptance "$ACCEPTANCE_RECORD" --approve-stable "$TAG" --publish`. It rechecks the qualification, the current protected `main`, the archive signature and the notarization flag recorded at packaging time, requires a private acceptance record for the exact build, and explicit release-maintainer approval of the exact tag. Stable is not published automatically.

If a promotion to Stable is interrupted, rerun `channel_release.py promote` with `--resume` and all evidence again. If a qualification is interrupted (it writes the candidate's metadata before refreshing the Dev feed), rerun `qualify` with the same arguments after checking the feed. If a local Dev publication is interrupted, inspect the remote release and feed state first (a reserved build number stays reserved) and then publish again. If a repository-wide lock is left behind, inspect the remote release and feed state before clearing it deliberately; never delete another run's lock.

## Credentials

The signing workflow takes private keys from configured secrets. Keep private signing material out of source, app resources and logs. Local publishing reads them from the macOS Keychain. The release workflows use these repository secrets, which are never printed: `REPOHUB_SPARKLE_PRIVATE_KEY`, `REPOHUB_CERTIFICATE_P12`, `REPOHUB_CERTIFICATE_PASSWORD`, `REPOHUB_SIGNING_IDENTITY`, `REPOHUB_NOTARY_KEY`, `REPOHUB_NOTARY_KEY_ID` and `REPOHUB_NOTARY_ISSUER`. The public verification key is the repository variable `REPOHUB_UPDATE_PUBLIC_KEY`.

## Rolling back

To roll back, restore the old application code in a new `main` change, pass the gate, and publish a higher build; Sparkle then offers it as a normal update. Old packages and releases are not deleted automatically, and a retained ZIP can be installed by hand if an app can't run its updater.
