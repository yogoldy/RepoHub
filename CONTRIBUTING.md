# Contributing to RepoHub

Thanks for helping. RepoHub is a backup tool, so the bar for changes is "does it keep your data safe and tell the truth", more than "does it work on my machine".

## Ground rules

These are the project's core promises. A change that weakens one will not be merged.

- **Never claim a backup is safe without evidence.** Green means verified contents **and** a macOS-confirmed upload of the current archive. Missing evidence prevents green. The panel identifies whether the comparison, freshness check or upload status is unavailable.
- **Never delete a backup before its replacement is verified and confirmed uploaded.** The one timed exception is documented (under latest-only retention, removed or excluded linked folders and checkouts enter a 30-day keep window and can be removed earlier on request).
- **Keep the helper local.** It listens on `127.0.0.1` only, and every write request checks Host, Origin and a per-process token. No arbitrary filesystem endpoints.
- **Keep backup operations read-only on source folders.** Preserve the Git probe safeguards and account for user- or system-configured filters.
- **Keep private data out of reports.** Diagnostic exports are sanitized. The report includes the text the user enters. Reports are previewed and sent only when the user chooses Send to GitHub or explicitly retries a failed send.

The reasoning and every past failure live in [docs/quality/FAILURE_MODES.md](docs/quality/FAILURE_MODES.md) and [docs/quality/golden-rules.json](docs/quality/golden-rules.json). A bug fix should add a small test that fails without the fix and register it there.

## What you need

- A Mac with Apple silicon and macOS 13 or later (the native app is macOS-only).
- Xcode or the Xcode Command Line Tools (`swiftc`).
- Python 3 (use a Python 3 interpreter with `tarfile` data-filter support) and Node.js (for the web tests).

## Run the tests

```bash
python3 -B -m unittest discover -s tests
(for file in tests/*.cjs; do node "$file" || exit "$?"; done)
```

The full release gate builds the native app, compiles and runs the native checks, and runs every golden rule. It needs a clean, committed tree and records its elapsed time in the gate receipt:

```bash
python3 tools/release_gate.py --require-clean
```

On uncommitted work, use the two commands above; the gate's package step refuses a dirty tree. Tests use synthetic folders and temporary servers. They never touch your real backups, iCloud or settings.

## Propose a change

1. Fork the repository and create a branch.
2. Keep changes small, one purpose per commit. Keep formatting changes, cleanup and behavior fixes in separate commits.
3. Follow the [readability standards](docs/READABILITY_STANDARDS.md): clear names, short functions with a clear job, and comments that explain why.
4. Add or update tests. Run the unit tests and the web tests.
5. Open a pull request. Project policy requires `automated-contract` to pass before merging into `main`. GitHub Actions runs that job on pull requests.

Please do not include real repo names, file paths, usernames or backup contents in commits, issues or pull requests.

## Reporting problems

- **Bugs and ideas:** use the app (**Settings → Help & diagnostics**) or open a GitHub issue.
- **Security problems:** do not open a public issue. See [SECURITY.md](SECURITY.md).

## Releases, signing and your own build

Official releases, the update feed, the update-signing key and the Apple signing identity are controlled by the official release process. The production bundle ID is constrained in code, the packager embeds the supplied feed and public key in Info.plist, and the native updater defines the official channel URLs. You can build and test the code and the Python and web parts freely. Producing your own signed, auto-updating build means replacing those identifiers, which is not documented yet. If you need that, open an issue and describe what you are trying to do.

The official release process is described in [docs/RELEASING.md](docs/RELEASING.md). It is for maintainers; you don't need it to contribute.
