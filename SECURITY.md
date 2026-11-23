# Security policy

## Reporting a vulnerability

Please report security problems **privately**, not in a public issue or pull request.

Use GitHub's private reporting: use the repository’s [private advisory link](https://github.com/yogoldy/RepoHub/security/advisories/new) if GitHub makes it available.

Please include what you found, how to reproduce it, and the version of RepoHub you tested, available in Finder’s Get Info for Repo Hub.app. Don't test against anyone else's Mac or data.

Security reports receive a best-effort response. Reports are acknowledged and handled as quickly as possible, and you will be credited if you wish.

## What is in scope

RepoHub runs on your own Mac and reads your folders, so these matter most:

- The local helper (`127.0.0.1:8767`): any way for a web page, another user or another process to read private data from it or make it write, delete or send something it shouldn't.
- The native app's bridge to its web panel, and anything that lets other content trigger native actions.
- Archive handling: restoring or verifying an archive writing outside where it should, or a backup being deleted without a verified, uploaded replacement.
- The update path: installing something that isn't an authentic RepoHub release.
- Diagnostics and bug reports leaking repo names, paths or file contents.

## Supported versions

Only the latest Stable release receives security fixes. Updates are offered inside the app (Settings → App updates).

## Known limitations

- **Shared Macs.** The helper listens only on `127.0.0.1`, and writes need a per-process token, but the session endpoint returns the token to local callers using the expected Host unless the request is marked cross-site. It does not authenticate the local user. On a Mac used by several people, another local user or process could read RepoHub's status (repo names and paths) or ask it to act. Use RepoHub on a Mac you don't share. Authenticating callers per user is on the [roadmap](ROADMAP.md).
- **Scanning a repo that has Git filters.** To count changes, RepoHub runs `git status`, which can run a filter command configured for a file. It first checks, without running anything, for clean, smudge or process filter commands in the effective Git configuration. It skips status for local, worktree or command-scope matches and when the check fails. User and system filters remain trusted. That check and the probe are two steps, so a process that rewrites a repo's config in the milliseconds between them could still get a filter run. Such a process already runs as you.
- **Maintainer release automation.** Dev-build qualification runs only for pushes to `main` of this repository, and verifies the successful Golden rules run and `automated-contract` job for that exact `main` push. Signing credentials are used only by a manually started validation, and pull requests from forks never receive them.

## Good to know

- RepoHub never asks for Full Disk Access or Accessibility, and has no telemetry. Its built-in external service endpoints are on GitHub: update checks and downloads, plus account checks, issue submission and delivery checks when you use GitHub reporting. A bug report is posted only when you choose **Send to GitHub** or explicitly **Retry send**, and only the exact preview shown is sent.
- Stable promotion requires Apple Developer ID signing and notarization. Dev also supports personal ad-hoc builds without notarization. Updates are additionally verified with an Ed25519 signature. The release workflow obtains private signing material from configured secrets. Keep production private keys out of Git.
