# Repo Hub agent instructions

- Use `/Users/leogoldberg/Desktop/repos/RepoHub` as the single working checkout. Switch regular branches there; do not create another worktree unless Leo requests one. See [working-copy guidance](docs/WORKING_COPY.md).

- This is the app foundation. Source repos and saved workspace JSON are user data; never change or commit their contents as part of app development.
- Keep the backend on loopback. Maintain Host/Origin/token write checks, safe path resolution, and revision checks.
- Preserve all existing backups. Do not introduce automatic retention deletion without Leo's authorization.
- Status JSON must report observed timestamps and backup results. Never claim an archive has uploaded to iCloud from local verification alone.
- Keep new modules separate from repository monitoring and backups. Prefer explicit adapters over arbitrary filesystem APIs.
- Use one task branch and commit your own changes before reporting completion. Report branch/SHA, unfinished work and deliberate skips. Never absorb unrelated working-tree changes.
- Run the synthetic backup/persistence/security tests and verify the installed status page. Compile the native app when native code or packaging changes. The Repo views UI is deliberately removed; preserve existing JSON and scoped APIs. Latest-only retention is authorized for app-managed snapshots: verify and persist the replacement, then require explicit macOS upload confirmation before cleanup; leave legacy backups intact. Missing upload signals must stay Unknown. Match checks must hash source file contents and verify archive bytes; do not turn metadata-only checks into green success.

## Golden-rule release contract

- Before promoting or deploying an application version, run `python3 tools/release_gate.py --require-clean` on its clean committed macOS source and inspect its JSON receipt. Missing/skipped referenced regressions, failed builds or dirty/mutated source cannot be accepted as release evidence.
- Use `docs/quality/FAILURE_MODES.md` and `docs/quality/golden-rules.json` when diagnosing regressions. A new failure needs a small controlled counterexample, appropriate diagnostic assertions, a narrow fix and an updated rule/gap. Keep private case data outside Git.
- For Leo’s personal Sparkle channel, follow [the approved delivery policy](docs/RELEASE_DELIVERY.md): an accepted protected main commit can publish after the automated gate; native testing follows delivery. Keep untested hardware/provider/UI conditions explicit. Publishing an update does not silently install it. Other deployments retain the changed-boundary checks in `docs/quality/RELEASE_GATE.md`; never substitute an older release’s receipt.

- GitHub `main` promotion must use a pull request with the required up-to-date `automated-contract` check from GitHub Actions. Do not bypass or disable protection to merge a failing version; no additional approving review is required. When Leo says “push to Git,” carry the complete agreed feature through this protected main flow as defined in [working-copy guidance](docs/WORKING_COPY.md); explicit local-only instructions override it.

## Readability for new and deliberately changed code

- Follow [the readability standard](docs/READABILITY_STANDARDS.md): clear names, multiline formatting, recognizable function responsibilities and comments explaining important decisions. Keep formatting, structural cleanup and behavior fixes in separate commits. This pointer does not authorize broad refactoring; use the [approved roadmap and stage authorization](docs/INTERACTION_TESTING_READABILITY_ROADMAP.md).
