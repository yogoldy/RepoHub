# Two-Mac reliability acceptance

This is the approved Air-first release protocol. No release acceptance is implied by the automated gate or harness preparation.

The fixed numbered matrix is [quality/reliability-matrix.json](quality/reliability-matrix.json). Run it unchanged on Air, then Pro, on the same Pro-built payload. Record each case as not_run, passed, failed or blocked in private evidence, with actual native UI observations, API snapshots, diagnostic references and protected-state checks. Any application fix produces a new candidate and restarts both host matrices.

## Guarded staging

`tools/reliability_acceptance.py package` requires a clean committed source and a matching macOS Golden Gate receipt. It copies that gate's native/cloud executables, the installer's declared runtime modules, web assets and known Git fixtures into one hashed payload. Transfer that directory preserving permissions; `prepare` refuses changed assets. Do not rebuild on Air. Fixture manifests include ignored/uncommitted files, Git history and empty directories. Alias picker choices resolve to two distinct same-named Project directories.

Each `prepare` creates a new owned `/private/tmp/repohub-acceptance-*` run. It has its own signed app identity, fake HOME/UserDefaults, state, manual scheduling and destination. During staging its unchanged native app is copied to a unique owned Applications directory and registered with LaunchServices; macOS rejected notification validation for the temporary-path copy. The journal and watchdog retain ownership evidence. Cleanup unregisters/removes only that exact copy when its assets still match; unexpected changes are preserved and reported. Provider observations use `/usr/bin/false`: missing upload evidence stays unknown. The run records macOS, architecture and Python versions, plus exact source/payload hashes. Signing provenance is recorded in the payload.

Before `stage`, demonstrate native control through local computer use on Pro and Jump Desktop on Air. Record that evidence privately. Supply only that host's known daily helper/app launch labels. The tool verifies loaded registrations and an idle daily backup, captures the actual data directory (including workspace-registry.json), schedules, configuration, notifications, app/runtime and launch plists, and copies rollback files privately. It never runs install.py, migrates personal backups, reads Keychain or alters existing launch plists.

A separately detached watchdog must report ready before any daily job is paused. A durable restore intent precedes every bootout. The staging jobs are uniquely named, and cleanup is locked/idempotent. Both the controller finally block and watchdog stop only owned jobs, compare protected files before restarting daily jobs, and restore paused registrations. `control` permits only scoped helper pause/resume/restarts, native restart and stop; it accepts no arbitrary command or PID. The watchdog has a bounded 30–3600 second lifetime. Never leave a run active while waiting for user input; stop it and inspect cleanup.json.

A production backup may have completed just before pause: any baseline disagreement stops staging and is investigated, not silently adopted. Protected data/runtime/config are hashed, but daily multi-gigabyte provider archives are not re-downloaded as a side effect of staging. Existing production backups are never a fault target. Exact archive-byte preservation assertions operate on owned synthetic fixtures.

## Commands

Run from the RepoHub checkout with the native build toolchain:

```sh
python3 tools/release_gate.py --require-clean --output /private/tmp/new-golden.json
python3 tools/reliability_acceptance.py package --source "$PWD" --gate /private/tmp/new-golden.json --output /private/tmp/new-payload
python3 tools/reliability_acceptance.py prepare --payload /private/tmp/new-payload
```

The copied payload includes a standalone harness for Air, where `/usr/bin/python3` is used. `stage --run RUN --python PYTHON --daily-label APP_LABEL --daily-label SERVICE_LABEL --control-evidence PRIVATE_FILE` runs a controlled session. Use `control --run RUN stop` to restore the daily app; inspect cleanup.json and the running daily helper/menu before reporting a blocker. Keep private logs and raw evidence out of Git.

## Permission and release boundaries

Real filesystem restrictions and a mounted disposable image complement regressions. They do not establish macOS TCC. Actual OS source-access and notification refusal/grant/revocation/restart evidence must use the staging identity or an isolated account. Never reset daily permissions, silently grant broader access, or default to Full Disk Access. Additional access/account or unavailable native control is blocked acceptance.

Only after every required case passes on both hosts: record acceptance/product thesis, require exact-head automated-contract, merge PR #6 with a protected merge commit, compare merged application sources to the accepted payload, and run clean main Golden Gate/current GitHub checks. Deploy sequentially Pro then Air with preserved configuration/rollback. Air's test-only monitoring list remains its own. Pro failure prevents Air deployment. Destination selection remains next.

## Air checkpoint — 2026-10-10

Candidate b97fdf2, built on Pro, was transferred unchanged and used on Air through
Jump Desktop. Pro is ARM64 macOS 27.0/Python 3.14.7; Air is ARM64 macOS
26.3.1/system Python 3.9.6. These are intentionally recorded differences.
The clean candidate macOS gate passed 188 tests with no skips; GitHub's candidate
checks passed. This checkpoint is **not release acceptance**.

| Case | Air evidence | Pro repeat |
|---|---|---|
| 01 | Passed native preflight, payload verification, isolation and protected-state baseline | Not run |
| 02 | Passed simultaneous three-alias selection to two distinct paths; cancelled draft made no write; reviewed removal/save retained IDs after helper/native restart and preserved old archive bytes. Re-add/removal subcase remains open | Not run |
| 03 | Passed visible expired-cache warning and reconnect; typed cache-expiry context retained original observation; zero unexplained disagreements. First-start and timeout subcases remain open | Not run |
| 04–06 | Not run on this two-host candidate; earlier regressions/disk-image evidence do not substitute this matrix | Not run |
| 07 | Blocked for current daily account: helper uses the same system Python identity as daily work. Actual privacy denial/restoration needs an isolated account | Not run |
| 08 | Diagnostic probe observed actual notification allowed/denied states, grant persistence across restart, and backup after revocation. Clean first-request refusal and full repeat remain open | Not run |
| 09 | Cleanup passed: protected hashes matched; daily Air jobs, test-only source list and idle helper restored. Same-candidate two-host completion remains open | Not run |

The notification investigation distinguished daemon rejection from user refusal:
`usernoted` could not validate the temporary-path client. Registering a separate
Applications copy permitted actual authorization observation. A development-signed
probe first established this behavior; the original ad-hoc candidate then also
reported real grant/revocation correctly from that location. Signing alone in the
temporary directory had not fixed it. Neither a daemon rejection nor an absent
prompt is counted as a user refusal.

Private case references: Air run 4dd895f42d2c499c9c5c2b7d20b7ce9b;
case02-cancel/saved/completed, case03-client-frames,
case08-registration-probe-os/applications-allowed/denied-backup, cleanup.
Raw logs, source paths, OS account identifiers and signing subjects remain outside
Git. A successful archive-content check found the synthetic edit made after
notification revocation. This avoids mistaking an old matched status for success.

No merge or daily deployment occurred; Pro remains unchanged. Before resuming,
provide an isolated test account for actual helper privacy evidence, then stage
with corrected registration and finish the unchanged matrix on both hosts.

The restored older daily Air menu still reports `EAGAIN`/“Resource deadlock avoided”
when reading its cloud copies. Restoration confirms the preserved installation,
not that its provider storage is healthy. This observation is retained separately;
no daily archive was modified or deleted to make it green.

Staging registration fix: fa69d95. Ten focused harness regressions passed. An
initial clean-gate attempt was correctly rejected because this checkpoint's
three documentation files were still uncommitted; it executed no test suite and
is not a test failure or accepted receipt. Commit the checkpoint before rerunning
the clean macOS gate. Both-host native acceptance remains pending.
