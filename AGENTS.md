# Repo Hub agent instructions

- This is the app foundation. Source repos and saved workspace JSON are user data; never change or commit their contents as part of app development.
- Keep the backend on loopback. Maintain Host/Origin/token write checks, safe path resolution, and revision checks.
- Preserve all existing backups. Do not introduce automatic retention deletion without Leo's authorization.
- Status JSON must report observed timestamps and backup results. Never claim an archive has uploaded to iCloud from local verification alone.
- Keep new modules separate from repository monitoring and backups. Prefer explicit adapters over arbitrary filesystem APIs.
- Use one task branch and commit your own changes before reporting completion. Report branch/SHA, unfinished work and deliberate skips. Never absorb unrelated working-tree changes.
- Run the synthetic backup/persistence/security tests and verify the installed status page. Compile the native app when native code or packaging changes. The Repo views UI is deliberately removed; preserve existing JSON and scoped APIs. Latest-only retention is authorized for app-managed snapshots: verify and persist the replacement, then require explicit macOS upload confirmation before cleanup; leave legacy backups intact. Missing upload signals must stay Unknown. Match checks must hash source file contents and verify archive bytes; do not turn metadata-only checks into green success.
