# Contributor guidelines

RepoHub is a backup tool, so these rules protect users' data. Start with the [README](README.md) and [CONTRIBUTING](CONTRIBUTING.md).

## Product rules that must not be weakened

- **Preserve backups.** Never delete a backup before its replacement is verified and macOS has explicitly confirmed its upload. The only timed deletion is the documented one: under latest-only retention, backups of linked checkouts and included linked folders that were removed or are no longer included are kept for 30 days and then deleted automatically. "Remove now" deletes one sooner only at the user's request. No other backup is deleted on a timer.
- **Never claim an upload without macOS's word.** Missing or unreadable upload signals stay Unknown. A percentage, even 100%, never confirms an upload. Match checks must hash source file contents and verify archive bytes; do not turn a metadata-only check into green success.
- **Keep the helper on loopback.** Maintain Host, Origin and per-process token checks on every write, safe path resolution and revision checks. Do not add arbitrary filesystem endpoints.
- **Never change the user's source folders.** Source repos and saved workspace data are user data. Do not change or commit their contents as part of app development.
- **Report observed facts.** Status JSON must report observed timestamps and backup results.
- **One status classifier.** A channel preference or any other setting must not redefine backup readiness or introduce a competing classifier of "backed up".
- **No private keys in a client.** Never embed Apple or Sparkle private signing keys in the app or the repository.

## How to work on the code

- **Use one task branch** and commit the changes for that task. Identify the revision under review and document any unfinished work or omitted checks. Never absorb unrelated working-tree changes.
- **Keep new modules separate** from repository monitoring and backups. Prefer explicit adapters over arbitrary filesystem APIs.
- **Test.** Run the synthetic backup, persistence and security tests, and compile the native app when native code or packaging changes. A new failure gets a small controlled counterexample, diagnostic assertions where useful, a narrow fix and an updated entry in [docs/quality/golden-rules.json](docs/quality/golden-rules.json) and [docs/quality/FAILURE_MODES.md](docs/quality/FAILURE_MODES.md). Keep private case data outside Git.
- **Run the gate before release.** Before qualifying or promoting a build, run `python3 tools/release_gate.py --require-clean` on clean, committed macOS source and inspect its JSON receipt. Missing or skipped referenced regressions, failed builds, or dirty or mutated source are not evidence. See [docs/quality/RELEASE_GATE.md](docs/quality/RELEASE_GATE.md).
- **Follow the readability standard** in [docs/READABILITY_STANDARDS.md](docs/READABILITY_STANDARDS.md): clear names, multiline formatting, functions with a recognizable job, and comments that explain important decisions. Keep formatting, structural cleanup and behavior fixes in separate commits. Propose broad refactoring separately.
- **`main` is protected.** Changes reach it through a pull request whose required `automated-contract` check from GitHub Actions has passed on the current head. Do not bypass or disable the protection to merge a failing change.

## Releases

Updates reach users through Sparkle, with a Stable channel (the default) and a Dev channel for testing. Publication never silently installs an app, channel promotion never rebuilds the archive, and Stable needs explicit approval of the exact package plus the recorded acceptance checks. The process is described in [docs/RELEASING.md](docs/RELEASING.md); it is for maintainers.

## Product intent

RepoHub should be usable without prior knowledge of its implementation. "Usable" means understandable, reliable and well explained, not monetized. Favor clear setup, permissions guidance, honest status text, useful diagnostics and recovery that an ordinary user can follow without knowing the implementation. Do not add service infrastructure only because a more elaborate design is possible.

RepoHub is released under the MIT License (see [LICENSE](LICENSE)). Bundled third-party components keep their own licenses.

## Privacy of this repository

The repository is public. Keep real repo names, personal paths, hostnames, email addresses and backup contents out of source, documents, commit messages, issues and pull requests. Use synthetic fixtures. Credentials and signing material never belong in Git.
