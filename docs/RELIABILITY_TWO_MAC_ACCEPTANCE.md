# Two-Mac reliability acceptance

This is the approved Air-first release protocol. No release acceptance is implied by the automated gate or harness preparation.

The fixed numbered matrix is [quality/reliability-matrix.json](quality/reliability-matrix.json). Run it unchanged on Air, then Pro, on the same Pro-built payload. Record each case as not_run, passed, failed or blocked in private evidence, with actual native UI observations, API snapshots, diagnostic references and protected-state checks. Any application fix produces a new candidate and restarts both host matrices.

## Guarded staging

`tools/reliability_acceptance.py package` requires a clean committed source and a matching macOS Golden Gate receipt. It copies that gate's native/cloud executables, the installer's declared runtime modules, web assets and known Git fixtures into one hashed payload. Transfer that directory preserving permissions; `prepare` refuses changed assets. Do not rebuild on Air. Fixture manifests include ignored/uncommitted files, Git history and empty directories. Alias picker choices resolve to two distinct same-named Project directories.

Each `prepare` creates a new owned `/private/tmp/repohub-acceptance-*` run. It has its own signed app identity, fake HOME/UserDefaults, state, manual scheduling and destination. Provider observations use `/usr/bin/false`: missing upload evidence stays unknown. The run records macOS, architecture and Python versions, plus exact source/payload hashes. Signing provenance is recorded in the payload.

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
