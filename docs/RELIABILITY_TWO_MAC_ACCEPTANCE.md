# Two-Mac reliability acceptance

This is the approved Air-first release protocol. No release acceptance is implied by the automated gate or harness preparation.

**One-time PR #6 exception (2026-10-16):** Leo authorized code integration into main before native acceptance finishes. [The exception and validation backlog](MAIN_INTEGRATION_EXCEPTION_2026-10-16.md) supersede the main-merge timing below for this PR only. Deployment and release approval remain blocked on their required evidence.

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


## Isolated-account preparation — 2026-10-10

The user created an isolated standard account on Air. Read-only account/group
checks confirmed it has no administrator membership. With explicit authorization,
Remote Login's selected-user list was extended only to that account. An installer
for the Pro's existing public SSH key is staged outside Git; it has not yet run
in the test account. No private key or password was copied.

Jump Desktop Connect is already installed machine-wide. Native inspection found
that the existing Air connection has Auto Logon saved for the daily account;
trying to switch at the lock screen returned the connection to that session.
Its saved settings were inspected and cancelled without edits. A temporary Jump
browser login is the next controlled connection attempt, with user-entered
credentials, preserving that existing connection. Native control of the isolated
account has not yet been established and is not counted as passed.

The current daily services have not been paused for this account preparation.
Actual helper privacy refusal/restoration, the full notification repeat and both
host acceptance remain open. Once test-account login and SSH are verified,
cross-account staging must coordinate daily-service restoration before occupying
the fixed native port; the current same-user stage command must not be invoked
as if the new account owned the daily installation. No main promotion or daily
reliability deployment has occurred.


## Isolated-account connection checkpoint — 2026-10-10

The user completed browser authentication and the isolated account's first Mac
login without sharing credentials. A refreshed Jump browser connection displayed
that account's desktop; Finder navigation and Terminal keystrokes established
actual native control. Bulk text insertion/clipboard paste did not reach the
remote Terminal, while individual keyboard events did. This input distinction
was observed before executing the setup command, rather than treating attempted
input as completion.

The account-scoped installer executed in the standard test account and confirmed
installation of the Pro's existing public key with restrictive forwarding options,
0700 directory and 0600 authorized-key permissions. The existing Jump native
connection's saved daily credentials remain unchanged. No private key or password
was copied or read.

SSH still rejected the account after installation. Read-only investigation found
an additional server-side AllowUsers rule limited to the daily username at the
Pro's existing Tailscale addresses. The Remote Login selected-user membership and
public-key fingerprint were correct; those checks alone did not establish usable
SSH access. A guarded administrator helper is prepared outside Git to add the test
username at exactly those same addresses, preserving the existing entries, saving
a rollback copy and checking SSH configuration syntax. Applying it awaits direct
user administrator authentication. Neither a wider network rule nor administrator
membership for the test account is requested.

This is a concrete connection-preparation blocker, not application failure or
permission-test evidence. No staging jobs were launched and no daily services
were paused. Cross-account restoration coordination remains necessary before
fixed-port staging. Actual privacy/notification acceptance, the complete matrix
on both Macs, protected merge and release deployment remain open.

At this checkpoint the clean macOS Golden Gate on fadf1cc passed all 190 Python
tests and JavaScript/native checks. Both exact-head GitHub automated-contract jobs
passed. The account/connection evidence changes documentation only; the application
payload is unchanged. The following documentation commit still requires its own
clean checks before being used as current evidence.


## Cross-account staging protocol — 2026-10-10

After the user's administrator step, BatchMode SSH authenticated as the standard
Air test account. Its directory/key file modes remain 0700/0600. The separate
server allowlist was the concrete connection blocker; resolving it does not
establish macOS folder privacy evidence. The daily helper/app stayed loaded.

The acceptance payload now also includes `reliability_account_guard.py`. The
same-user `stage` command remains available for same-user cases, but must not be
used to pretend a standard account owns the daily installation. For isolated
permission acceptance:

1. In the test account, prepare the verified payload, then run the account guard's
   `peer --run RUN --seconds SECONDS`. Keep the run private; only its synthetic
   coordination receipt and read-only lock are readable across accounts.
2. In the daily account, run `hold --coord COORD --python PYTHON --daily-label
   APP_LABEL --daily-label SERVICE_LABEL --control-evidence PRIVATE_FILE`. It
   captures its own protected state/rollback and starts its own detached watchdog
   before pausing anything. Record the returned daily-hold directory.
3. In the test account, run `stage --run RUN --hold HOLD --python PYTHON
   --control-evidence PRIVATE_FILE`. It verifies the held candidate/owner/port,
   starts its own watchdog and launches only its own fixture helper/native jobs.
4. Stop the test with its scoped harness `control --run RUN stop` or account-guard
   `cleanup --run RUN`. Confirm owned jobs are gone and the peer is stopped; the
   daily hold then restores its own registrations. Inspect both cleanup records,
   protected hashes and the actual daily helper/menu before continuing.

The same read-only file lock excludes restoration racing test startup. An active
lease blocks restoration even before the test helper binds the port; a test cleanup
failure keeps it active. Restoration also refuses an unknown service on that port.
Neither account runs cross-user launchctl, reads the other's private state, nor
needs sudo for acceptance. Deadlines are bounded; independent watchdogs continue
cleanup after controller loss. Real interruption/cleanup checks must run before
using this guard for destructive fixture cases. Seven scoped regressions pass;
full clean-gate and live cross-account validation follow this commit.


## First cross-account guard run — 2026-10-10

Pro-built candidate 5ec10cf passed the clean 197-test macOS gate. The first transfer
was rejected before staging because extraction umask changed file modes despite
matching content hashes. A fresh `tar -xpf` transfer preserved the manifest exactly;
the rejected copy remains private for diagnosis. Transfer permissions must be
preserved, not waived in validation.

The first daily-account hold then failed its immediate port-drain check after
launchctl bootout. Protected hashes matched, and no test-account jobs were launched.
Its detached watchdog recovered autonomously: both daily labels were restored and
the protected baseline remained unchanged. This establishes real restoration after
a failed preflight, not the planned active-test controller-kill or permission cases.
A bounded five-second port-release wait and two required regressions address this
shutdown timing race. A fresh clean candidate/lease is required before repeating.


The port-only follow-up isolated another cross-account constraint: with no 8767
listener and old connections in TIME_WAIT, the daily UID could bind but the test
UID received errno 48. It cleared for the test UID after 15.1 seconds. The probe
launched no test app; cleanup restored both daily labels with matching protected
hashes. The receiving account now performs its own bounded 45-second drain check
and records typed per-condition admission evidence. Corrected native staging and
active controller-loss acceptance still require a fresh clean candidate.


## Air isolated-account preflight and real interruption — 2026-10-10

Candidate 36d76c0 passed the clean macOS Golden Gate: 201 Python tests and all
JavaScript/native checks. Both exact-head GitHub automated-contract jobs passed.
The Pro-built payload manifest was verified unchanged after permission-preserving
transfer; no independent Air build was used.

Private probe reference: 754681d028d64bea9ad0f4f762769109. All nine recorded account
admission checks passed, including receiving-user port release. Native menu-bar
control worked in the standard test account. Its initial Settings flow showed
unchecked access and optional unrequested notifications; Check access then showed
both fixture sources and the destination accessible, matching helper API evidence.
Login operation was accurately not confirmed for this isolated installation. The
provider stayed unknown. Two recorded native repo frames had zero presentation
or input disagreements. These are preflight observations, not the full matrix.

A controlled SIGKILL targeted only the verified owned test controller. The test
watchdog stopped both exact test labels, unregistered/removed its unchanged owned
Applications copy and released its lease. The daily controller returned a waiting
result while the other UID's port drained; its independent watchdog continued
until both original daily labels were restored. Both cleanup records confirmed
protected preservation without capture, registration or restore errors. The
restored daily helper reported its original five test-only sources and was idle.

This closes real cross-account cleanup/controller-loss preflight on Air. It does
not close native folder-selection, freshness, filesystem/volume fault or actual
OS privacy/notification cases on this candidate, nor the Pro repeat or release.
No source/destination fault was performed during the probe, and no daily backup,
schedule, credential or launch plist was changed. The accepted app payload remains
36d76c0; this checkpoint is documentation only. Start a fresh owned run for the
remaining unchanged matrix, preserving that application payload on both hosts.


## Air isolated-account native checkpoint — 2026-10-10

Private run reference: 3cfb181c1e484ad6baba574ef029564d. The unchanged Pro-built
36d76c0 application payload was staged again under the account watchdogs. The
documentation-only 7f3f51c head passed a clean 201-test macOS gate and both current
GitHub automated-contract checks. This is a partial acceptance record.

- Native simultaneous selection of three aliases resolved to two distinct
  same-named Project paths. The initial mis-targeted picker draft was cancelled;
  exact registry equality proved it made no saved change. List-view selection
  then made the intended multi-selection visible before Choose. Draft removal,
  exact-path review/save, distinct IDs, existing-ID retention and helper/native
  restart persistence passed. Previous Project/Accessible archive bytes remained
  unchanged after monitoring removal. The reviewed re-add/removal repeat remains
  open; this does not close all of case 02.
- Settings Check access matched the helper for the accessible fixture sources and
  destination. Custom staging labels correctly did not claim daily login
  registration. With provider observations disabled, a later verified local
  backup displayed Awaiting confirmation and cloud status unknown.
- A synthetic Desktop source was readable to the SSH caller but the actual
  background helper rejected its review with EPERM. The saved source registry
  remained unchanged. No visible folder prompt or helper-specific Files & Folders
  entry was obtained. Restarting that exact owned helper from native Test Terminal
  retained its program arguments and reproduced the denial. This establishes a
  helper/caller access difference, not an explicit macOS user refusal.
- The contextual notification request showed an actual system banner and the
  staging identity's Notifications page. Authorization was initially denied; the
  request eventually reported failed. System Settings grant produced allowed;
  revocation plus native restart produced denied and the menu disclosed macOS
  permission needed. A subsequent synthetic edit was found inside a newly
  verified archive. Initial explicit prompt refusal remains unproven; a daemon
  error or initially disabled switch is not substituted for user refusal.
- The private diagnostic checkpoint contains 700 events and zero recorded input
  or presentation disagreements. This is limited to the observed frames, not a
  claim that the remaining fault cases or every UI state passed.

Read-only session evidence showed a completed remote Test login that was not the
active console session; the console belonged to the login screen. This is a
possible permission-prompt variable, not a proven explanation. Ask the user to
unlock that test account locally before continuing actual privacy acceptance.
No daily privacy identity was reset and no Full Disk Access was requested.

The owned test jobs stopped and the registered staging copy was removed. Both
independent cleanup receipts reported protected preservation; the daily watchdog
restored both original labels with no restore/capture errors. The daily API again
showed its original five test-only sources and idle backup. Synthetic fixtures and
private evidence remain available for diagnosis; they are not production data.
The Pro is unchanged. Cases 03–06, complete 02/07/08, same-candidate Pro acceptance,
protected merge and deployment remain open.


## Helper attribution investigation — 2026-10-10

The documentation checkpoint 0b95cb6 passed both exact-head GitHub
`automated-contract` runs (38104689893 and 38104686494), following its clean
201-test macOS gate. The application payload remains 36d76c0. Required native
acceptance is still open; passing automation does not close permission evidence.

Apple's current [On File System Permissions](https://developer.apple.com/forums/thread/678819)
guidance distinguishes a GUI login session from non-GUI execution and explains
that Files & Folders prompts depend on responsible-code attribution. It recommends
`AssociatedBundleIdentifiers` for a launch agent whose access is not attributed to
its app. The production installer and both staging plist builders currently omit
that property and launch the helper through a system Python interpreter. These are
observed packaging facts and an attribution hypothesis, not proof of the Air's
EPERM cause. A remote GUI login being off the physical console also does not prove
that it is a non-GUI execution context.

Next controlled investigation: first observe the user's locally unlocked Test
console and retry the unchanged helper in a fresh guarded run. If denial persists,
retain original denial evidence and compare the isolated job's responsible-code
attribution with Apple's guidance. Any association/signing fix must be narrow,
regression-tested and make a new same-payload candidate for both-host acceptance.
A successful native picker or caller read must not substitute for a helper read.
Do not grant Full Disk Access, reset daily permissions, or count a configuration
hint as actual macOS refusal/restoration evidence.


## Air local-console attribution experiment — 2026-10-11

Private run reference 7c57f4c7eb3446c1afb6104898bcc6e2 used unchanged 36d76c0
fixtures/app with separately recorded launch experiments. The physical console
was RepoHub Test, native Terminal keyboard control worked, and a bounded owned
caffeinate assertion prevented idle system/display sleep. Provider reporting
remained disabled. The original helper still returned EPERM for a fresh synthetic
Desktop source; its saved registry stayed identical. Association-only and direct
Python experiments also failed that same review without a visible prompt.

Filtered system evidence identified the helper's responsibility as Apple's
Python/tool shim. A tiny independently identified native launcher was built only
on the Pro, signed, hashed, transferred unchanged and registered as a disposable
probe. Entering the same Python/helper/config through that native bundle produced
an actual Desktop prompt. Explicit Don't Allow returned a denied review with no
registry write. The user restored that probe's Desktop permission through native
System Settings and authenticated directly; the same helper then returned a
successful three-path review, still without changing the saved registry.

The probe's jobs were stopped by the scoped cleanup. The unchanged owned probe
and staging Applications copies were unregistered/removed. Test and daily cleanup
receipts both confirmed protected preservation. The daily watchdog restored both
original labels without errors; the daily API again reported its original five
sources and idle backup. Private system logs, credentials and file paths are not
in Git. The bounded caffeinate process remains available for the next test run
and expires automatically; it changes no permanent sleep setting.

This establishes the packaging counterexample and motivates the native helper
entry fix in this commit. It does not count as final-candidate case 07 acceptance:
no saved Desktop monitoring/restart/archive lifecycle was completed in this probe,
and the other matrix groups and Pro repeat remain open. Rebuild/gate/transfer the
new candidate and run the entire same-payload matrix on both hosts before merge
or deployment. Nothing was installed as either machine's daily release.


## Native-launch candidate checkpoint — 2026-10-11

Application candidate `71998b0` passed the clean macOS Golden Gate: 204 Python
tests, zero skips, plus JavaScript/native builds and checks. Both exact-head
GitHub automated-contract jobs passed. One Pro-built payload was transferred to
Air preserving modes; its manifest SHA256 is
`e81baa6bcfa4a9878c85f3e2729d480500db4fb836a0a3684f12d88f14e636a9`.
No Air rebuild, daily installation, main merge or release acceptance occurred.

The fresh isolated-account run used the real candidate's native helper launcher,
not the earlier diagnostic probe. Its physical console was the test account, and
Jump Desktop supplied visible native control. The background helper's source
review produced the actual macOS Desktop-access prompt. Clicking **Don't Allow**
returned a blocked review; the saved workspace-registry hash was unchanged. The
candidate's own Files & Folders entry then exposed Desktop access. Restoration
requires direct user administrator authentication and remains pending at this
checkpoint. Saving a Desktop source, revocation after a baseline archive and
restart/recovery still need evidence; case 07 is not passed.

Real POSIX restrictions on the synthetic Project root and a nested tracked file
produced accurate native access-denied states. The root case kept its verified
archive bytes intact while an accessible sibling archived a known new edit.
Restoring access recovered the same workspace ID. In the nested-file case the
menu displayed the verification-read failure and scoped retry control; a new
terminal backup run recorded failure without replacing the previous archive,
while the sibling's known edit was present in its archive. Restoring permissions
recovered and archived a known recovery edit. These failures did not claim an
actual macOS privacy refusal from errno alone.

Notification authorization was exercised through the actual candidate's menu
and macOS Settings. The initial contextual request ended with a failed request
callback and OS permission denied; it is **not** counted as an explicit user
refusal. Switching the isolated application's Allow notifications on/off produced
corresponding allowed/denied observations. A known edit was found inside a new
archive after revocation; upload remained unknown with the provider disabled.
The full notification request/refusal/restart lifecycle remains open (case 08).

Diagnostic evidence includes 36 actual reported UI frames and zero
presentation-input or cross-view disagreement events across the recorded window.
This describes the observed frames, not unobserved screens. Private references:
Air run `d1425da2d92345f5932d29faac70f139`; case01-api,
case07-before/refusal, case04-root-before/blocked/completed,
case04-nested-final-denied/recovery-final, case08-allowed/denied-backup,
case01-04-08-diagnostics, checkpoint and cleanup. Raw paths, OS exception prose,
credentials and logs remain outside Git.

A test-controller polling mistake initially watched the top-level repo error
rather than nested verification failure; an unrelated guessed retry route was
rejected with 404. These attempts are not accepted assertions. The clean nested
repeat recorded the actual verification error and a changed backup run ID with
a terminal failure, plus unchanged archive bytes and the sibling edit. A 202
response or the previous idle state is never evidence that the requested backup
completed. Future controlled cases must correlate the new run's terminal result.

Before waiting for authentication, both independent watchdogs completed cleanup:
owned candidate jobs stopped, registered candidate copy removed, protected state
hashes unchanged, and both daily Air registrations restored. The running daily
helper again reported its original five test-only sources and an idle backup.
A bounded two-hour test-account caffeinate assertion prevented idle sleep during
native testing; no permanent sleep settings were changed.

Cases 02, 03, 05 and 06 have not run on this new application candidate. The Pro
repeat, final permission lifecycles, protected promotion and both deployments
remain unfinished. This documentation changes no application payload.


## Desktop grant and restart recovery — 2026-10-11

After the user authenticated the actual candidate's Desktop grant directly in
macOS, unchanged application payload `71998b0` was staged again under fresh
isolated state. The background helper successfully reviewed three synthetic
paths without modifying the registry. A reviewed save established the Desktop
source alongside two accessible fixtures, preserving their distinct identities.
All three baseline archives verified locally; provider observations remained
disabled and the native menu correctly displayed awaiting confirmation.

The scoped helper and native app were restarted. Workspace IDs persisted, and
the helper archived a known new Desktop file after restart. Acceptance correlated
the new archive's contents with its terminal `backup_finished` event, rather
than accepting an HTTP 202 or a previous idle status. All three earlier verified
archives retained their exact SHA256 values. The actual native Settings panel
showed all sources and the destination as Access checked, helper running, and
notifications denied with backups still operational. The isolated launch labels
correctly remained unconfirmed as production login registration. Diagnostic
evidence contained zero presentation-input or cross-view disagreements.

Two controller assumptions were corrected in private evidence: manual source
configuration legitimately has a null `repos_root`, so ownership checks use the
exact destination and saved identities/paths; an archive inspection without a
terminal-event/content assertion was premature. Neither attempted assertion is
counted as a product failure or successful acceptance. The clean repeat checked
the actual new file bytes, terminal run ID, archive preservation and readiness.

Refreshing macOS Settings was necessary to show the newly registered candidate
entry. Turning off that entry's Desktop access to exercise post-backup revocation
opened another native administrator/Touch ID prompt. Authentication remains a
direct user action; revocation and subsequent recovery are still open. No daily
permissions were reset and Full Disk Access was not requested.

Before handing off that prompt, both watchdog cleanup receipts confirmed
protected-state preservation, owned candidate jobs stopped and registration
cleanup without errors. Both original daily Air jobs were restored; the live
daily helper reported its original five sources and idle backup. Pro remains
unchanged. Private evidence references: Air run
`1e0aa4e89b6046afa839cf299039ced5`, case07-restored-review,
case07-granted-baseline, case07-restart-recovery and both cleanup receipts.
No private paths, credentials or raw logs are published here.

This is partial case 07 evidence, not release acceptance. Post-backup privacy
revocation/restoration, the complete notification lifecycle, cases 02/03/05/06
on this payload and the identical Pro matrix remain required. Read-only checking
found no isolated Pro test account yet; real Pro privacy tests therefore also
need account preparation. No merge or daily deployment occurred. This checkpoint
changes documentation only; the accepted application payload is unchanged.
