# Repo Hub agent instructions

- Use `/Users/leogoldberg/Desktop/repos/RepoHub` as the single working checkout. Switch regular branches there; do not create another worktree unless Leo requests one. See [working-copy guidance](docs/WORKING_COPY.md).

- This is the app foundation. Source repos and saved workspace JSON are user data; never change or commit their contents as part of app development.
- Keep the backend on loopback. Maintain Host/Origin/token write checks, safe path resolution, and revision checks.
- Preserve all existing backups. Do not introduce automatic retention deletion without Leo's authorization.
- Status JSON must report observed timestamps and backup results. Never claim an archive has uploaded to iCloud from local verification alone.
- Keep new modules separate from repository monitoring and backups. Prefer explicit adapters over arbitrary filesystem APIs.
- Use one task branch and commit your own changes before reporting completion. Report branch/SHA, unfinished work and deliberate skips. Never absorb unrelated working-tree changes.
- Run the synthetic backup/persistence/security tests and verify the installed status page. Compile the native app when native code or packaging changes. The Repo views UI is deliberately removed; preserve existing JSON and scoped APIs. Latest-only retention is authorized for app-managed snapshots: verify and persist the replacement, then require explicit macOS upload confirmation before cleanup; leave legacy backups intact. Missing upload signals must stay Unknown. Match checks must hash source file contents and verify archive bytes; do not turn metadata-only checks into green success.

## Product intent and ordinary-user experience

- RepoHub is intended to be an open-source application usable by people other than Leo, not only an owner-operated development tool. "Productizable" means understandable, reliable and usable; it does not imply monetization or proprietary distribution.
- Preserve the work toward clear setup, permissions guidance, status explanations, useful diagnostics/reporting, coherent interface behavior, CI and safe updates. Favor sensible defaults and recovery that ordinary users can understand without knowing the implementation. Do not add service infrastructure solely because a more elaborate design is possible.
- Ordinary installations follow Stable. Dev/Testing offers are deliberately enabled locally for Leo's Pro and Air; keep experimental controls out of the ordinary settings flow. Public source and publicly downloadable experimental packages are acceptable. Offer isolation is not access control: do not add private hosting, device authentication, hardware allowlists or download credentials for this requirement. Never embed Apple/Sparkle private signing keys in a client.
- Keep normal update delivery seamless and preserve the tested-package promotion and acceptance checks. A channel preference must not redefine backup readiness or introduce a competing status classifier.
- License selection remains Leo's decision. Public visibility was verified on October 20, but no project license file was found; do not silently select a license or imply that this choice is settled.

## Golden-rule release contract

- Before Testing delivery or Stable promotion, run `python3 tools/release_gate.py --require-clean` on clean committed macOS source and inspect its JSON receipt. The sole Dev exception is `python3 tools/dev_gate.py --output <new-private-receipt>` plus the staged publisher's native/package/signature checks on the exact committed source. Dev is local-Pro publication only and cannot move public latest. Missing/skipped referenced regressions, failed builds or dirty/mutated source cannot be accepted as evidence for the requested tier.
- Use `docs/quality/FAILURE_MODES.md` and `docs/quality/golden-rules.json` when diagnosing regressions. A new failure needs a small controlled counterexample, appropriate diagnostic assertions, a narrow fix and an updated rule/gap. Keep private case data outside Git.
- Follow [staged delivery](docs/RELEASE_DELIVERY.md) and [the channel contract](docs/UPDATE_CHANNELS.md): accepted main may publish Testing after the complete gate; Stable requires explicit exact-package approval, both-host installed acceptance and notarized Developer ID signing. Preserve native evidence gaps. Publication never silently installs an app. Channel promotion does not rebuild the archive, change daily permissions or bypass protected main.

- GitHub `main` promotion must use a pull request with the required up-to-date `automated-contract` check from GitHub Actions. Do not bypass or disable protection to merge a failing version; no additional approving review is required. When Leo says “push to Git,” carry the complete agreed feature through this protected main flow as defined in [working-copy guidance](docs/WORKING_COPY.md); explicit local-only instructions override it.

## Readability for new and deliberately changed code

- Follow [the readability standard](docs/READABILITY_STANDARDS.md): clear names, multiline formatting, recognizable function responsibilities and comments explaining important decisions. Keep formatting, structural cleanup and behavior fixes in separate commits. The [current product roadmap](PRODUCT_THESIS.md#next-delivery-sequence) incorporates the former interaction-testing plan. Broad refactoring and the representative teacher review remain deferred and require separate scope approval.
