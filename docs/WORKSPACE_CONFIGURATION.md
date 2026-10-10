# Workspace configuration foundation (Tier 3A)

Registry implementation: `4363423`, with ID-scoped presentation/diagnostic follow-up on `codex/workspace-setup`. This is the persisted source model and API that the future setup interface will use. Folder pickers, destination selection, visual onboarding and readable backup-folder names remain separate roadmap items. The installed Macs were not updated in this pass.

## Registry and identity

The authoritative source list lives in `state_dir/data/workspace-registry.json`. It is atomically saved with owner-only file permissions, included in the helper-data archive, and preserved across helper restarts. An invalid or symlinked registry fails closed rather than being silently reset.

```json
{
  "schema_version": 1,
  "source": {"mode": "home", "home": "/absolute/repos"},
  "workspaces": [
    {"id": "Example-d029f87e3d", "path": "/absolute/repos/Example", "active": true}
  ]
}
```

IDs are stable internal references, independent of archive content hashes. Existing repo-home installations retain the original name-derived IDs, backup index entries, scoped JSON, per-repo settings and schedule clocks. Automatic discovery of new immediate children uses the established name-derived ID unless it collides with a retained identity. New explicit selections use canonical path-derived IDs; two folders with the same name at different paths remain distinct. IDs must not be reconstructed by a client from a display name.

Deactivated entries stay in the registry so reselecting the same location restores its identity. Removal changes monitoring only: it does not delete the source, saved JSON, schedules or current archive. Moving a source to a different path is not automatically inferred as an identity-preserving rename; explicit source relocation and archive-folder naming migration are future work.

## Source modes

| Mode | Selection | Behavior |
| --- | --- | --- |
| `home` | One existing containing folder | Monitor each immediate, non-hidden, non-symlink child directory, including directories without Git. Discover new children on subsequent reads/scans. |
| `manual` | A list of existing folder paths | Each selection is one workspace. Canonical aliases are deduplicated; an empty list pauses repo monitoring. No shared parent is required. |

The first startup without a registry migrates `config.json`'s existing `repos_root`. For a fresh installation without that legacy key, an explicit initial `sources` value can be supplied:

```json
{
  "sources": {"mode": "manual", "paths": ["/absolute/project-a", "/another/project-b"]},
  "backup_root": "/absolute/destination/Snapshots",
  "state_dir": "/absolute/RepoHub-state"
}
```

After creation, the saved registry takes precedence over the legacy home and initial `sources`; editing those initial settings does not silently replace an approved source list. The destination is still configured by `backup_root`; choosing/migrating it in the UI belongs to 3D/3E.

## Selection and filesystem boundaries

Paths must be absolute and resolve to existing directories when selected. Parent/child selections are rejected rather than archived twice. Sources must not equal, contain or sit inside the backup or application-state folders; aliases are checked against their physical location. Hidden/symlink children are excluded from home discovery. Explicit symlink aliases are resolved to a canonical directory at selection time.

Missing active folders stay visible with a source error. Scanning/backups check that an approved path still resolves to the same canonical directory and reject a replaced symlink or unavailable source. A missing directory cannot be mistaken for an empty workspace and replace a good archive. An unreadable folder produces a scan/backup error rather than omitting unreadable entries. This is path validation, not a filesystem snapshot: concurrent mutation and volume/permission changes remain live acceptance cases.

## Local API

`GET /api/workspaces` returns `configuration` plus its SHA-256 `revision`. The configuration includes inactive identity records as well as active entries; it is local app data and is not a shareable diagnostic payload.

`POST /api/workspaces` accepts exactly `source` and the last-read `revision`:

```json
{
  "source": {"mode": "manual", "paths": ["/absolute/project-a", "/another/project-b"]},
  "revision": "<revision returned by GET>"
}
```

For home mode, `source` is exactly `{"mode":"home","home":"/absolute/repos"}`. Unknown fields and invalid selections are rejected. Existing loopback Host, same-Origin and process-token checks apply. A stale revision or busy scan/backup returns 409; the caller must review the current state before retrying. Persistence failures preserve the previous selection. Saving does not launch a backup.

Configuration saves and backup source selection share the backup lock, while saves also acquire the scan lock. A backup cannot capture the old selection, allow a removal to be saved, and then copy that removed source. Automatic home discovery changes the revision, so a stale setup preview cannot overwrite newly discovered identities.

Scanners, schedules, scoped JSON APIs and backups obtain their sources from this registry. Status includes `source_mode`, `workspace_sources` (exact active ID/path pairs), and `repos_root` only for home mode; `repos_root` is null for manual mode. The native Finder action still accepts only an ID from the exact top-level menu page. It resolves that ID against fresh status and the approved ID/path pair, rejects duplicate/mismatched pairs, and checks the actual directory. The new native bridge retains compatibility with the older single-root helper.

## Diagnostic and test evidence

Successful saves record `workspace_configuration` with enumerated `mode`/`result` and bounded repo count. Source names and paths are not logged by that event or exposed through its sanitized export. Existing repo/run/archive events explain the subsequent scans and backups; a configuration event alone is not backup or upload proof.

[GR15](quality/FAILURE_MODES.md#gr15--workspace-selection-preserves-identity-and-copy-scope) requires every workspace regression to execute in the Golden Gate. Tests cover migration, duplicate names/aliases, missing or retargeted sources, overlap/protected folders, inactive identity reuse, saved-manual authority, stale/busy/write-failure handling, backup/configuration interleaving, diagnostic privacy and API guards. Backup activity carries `current_repo_id`, and each per-repo failure carries `repo_id`; the human-readable name remains a label. UI status, diagnostic projections and problem episodes use those IDs to distinguish same-named folders, falling back to legacy names only when the ID field is absent. Native bridge checks cover approved manual locations, absent IDs, mismatched paths, malformed approvals and duplicate IDs even when their paths differ.

A development smoke run used an actual helper process on a separate loopback port with temporary folders, manual-only schedules and unavailable provider observations. Sixteen assertions verified API selection, distinct same-name identities, complete archive manifests/digests, the registry in helper-data backup, real restart persistence, non-destructive removal and diagnostic evidence. Fixtures were removed; private receipts/logs remain outside Git. The Pro's existing status API/menu remained reachable and its installed helper still matched main.

Native compilation/URL tests do not prove an actual Finder click for a manual selection. Native picker interaction, separate-volume removal/remount, inaccessible-volume recovery, sustained concurrent writes, setup layout and provider upload evidence remain unchecked for this new configuration flow. No new iCloud upload, two-device restore, app installation or main promotion is claimed here.
