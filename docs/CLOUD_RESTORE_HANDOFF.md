# Controlled receive-and-restore audit

## Purpose and exact claim

The cloud agent is the independent computer that **receives** an archive downloaded from iCloud. It does not retrieve from iCloud, authenticate to Apple, connect a drive, or use the Mac's cached archive as a substitute. Receiving an archive and restoring it is the agreed milestone. Direct remote retrieval remains separate.

A pass means: **the supplied archive matches the trusted expected archive checksum and restores to the supplied independently captured source baseline, with contained Git integrity/history checks passing where applicable.** It does not prove Apple provenance, future backups, every repository, or that the restored application runs.

## Pin and disclose the controls

| Variable | Control/evidence |
| --- | --- |
| Verifier source | Pin the exact handoff commit on `codex/backup-change-detection`; record `git rev-parse HEAD` and `git status --porcelain` before starting. Do not silently update the verifier. |
| Archive identity | Exact expected SHA-256 taken from the app's recorded backup receipt, not recomputed from the received archive to create the expectation. |
| Source expectation | `expected.json` captured by the local source-inventory command; it must describe the same content point in time as the chosen backup. Never derive it from the tested archive. |
| Baseline transfer | Expected SHA-256 of `expected.json` supplied separately in the trusted handoff. The tool checks it before parsing. |
| Download provenance | User records archive identity, download method/date and whether it came from iCloud.com. The verifier cannot authenticate that statement. |
| Restore destination | New private directory per run; existing outputs are refused. Never restore over a working repo. |
| Toolchain | Python standard library and installed Git; log versions, platform, verifier-file hash, Git subcommands, exit codes and output digests. No dependency install is needed. |
| Execution/network | Do not execute restored code or hooks, run its tests, install its dependencies, contact remotes, or change global Git/system config. Git commands explicitly disable hooks, fsmonitor, lazy fetch, prompts and all transport protocols. Cloud egress should be disabled after the inputs arrive; document the actual environment network setting. The script itself is not an OS network sandbox. |
| Limits | 250,000 entries, 8 GiB expanded file bytes, 8 GiB compressed input, 128 MiB baseline JSON, 120-second Git-command timeout. Insufficient VM disk/memory is a failed/incomplete run, not a pass. |
| Immutable inputs | Record hashes at start/end and check source/input changes during capture/verification. Do not edit or regenerate inputs to make a failure pass. |
| Deviations | Record every departure from the handoff before the test. Missing inputs or unsupported cases stop the test; disclose them. |

We can control and disclose known variables; no test can guarantee that unknown variables do not exist. OS/filesystem/tool behavior remains part of the recorded test environment.

## Local source-baseline preparation

This runs on Leo's Mac, **not in the cloud**. Select a particular backup receipt and its repo. The source must still represent that backup's content point in time. If it has changed, do not manufacture a historical baseline from the archive: choose an unchanged repo or coordinate a new backup and independent capture while editing is paused. Finder-only differences are real differences for this audit; there is no `.DS_Store` exception here.

Choose a new private directory outside monitored repos, the source folder and the tracked checkout. Capture all regular-file bytes, permissions, directories and symlink targets, including `.git`, ignored files and uncommitted files:

```sh
python3 -B restore_audit.py capture \
  --source '<absolute-local-source-repo>' \
  --archive-sha256 '<trusted-SHA256-from-backup-receipt>' \
  --out '<new-private-baseline-directory>'
```

`expected.json` and its checksum in `result.json` are the handoff baseline. The source is checked for changes while capturing, including after read-only Git checks. Capture success is not restore success and does not establish that an older archive matches the current source. Record the receipt's backup time separately from the baseline capture time.

## Inputs the cloud agent must receive

1. The actual `.tar.gz` backup downloaded from iCloud, privately provisioned into the task filesystem.
2. `expected.json`, independently captured from the matching live source.
3. Its trusted SHA-256, sent separately from the file.
4. A brief user provenance statement and the expected source/backup time-point alignment.

The public GitHub repo supplies **only the verifier, tests and instructions**. A GitHub clone is not a substitute for the backup. Never commit/archive private inputs, manifests, extracted trees or logs in Git; keep them outside the checkout. They may contain secrets and private filenames. Do not put secrets or public download URLs in issues or the environment's published prepared filesystem. Provision each actual private test input only through a user-authorized transfer route.

## Cloud agent instructions

1. Confirm the pinned verifier revision is checked out and unchanged. Record the source revision and command transcript in a private `agent-notes.md`, outside Git. Confirm the three required verification inputs actually exist; if not, stop with a precise list of missing inputs. Do not ask for iCloud access.
2. You may run synthetic tests first. Record them separately and label them **synthetic harness validation**, not personal/cloud restore success:

   ```sh
   python3 -B -m unittest discover -s tests -p test_restore_audit.py -v
   ```

   Expected negative tests print `Audit failed:` messages and still result in a successful unittest run. Distinguish these from failure of the test suite.
3. Record the actual cloud network setting and available disk space. Use a fresh private output directory outside the checkout, with enough space for both the received archive and restored bytes. No restored-code execution or app dependency install.
4. Run exactly:

   ```sh
   python3 -B restore_audit.py verify \
     --archive '<received-archive-file>' \
     --expected '<received-expected.json>' \
     --manifest-sha256 '<separately-supplied-baseline-SHA256>' \
     --out '<new-private-restore-output>'
   ```

5. Save the command, exit code, exact verifier Git revision and input-transfer/provenance statement in `agent-notes.md`. The tool produces private `events.jsonl`, `result.json`, and the isolated `restored/` tree. Logs record stages, versions, identities, durations and Git command return codes/output digests; they do not print file contents or raw Git outputs. A missing result or nonzero exit is not a pass. Do not modify the archive, expectations or verifier and rerun silently; any revised experiment needs a new output directory and disclosed rationale.
6. Report the archive checksum, manifest checksum, entry count, Git verified/not-applicable result, final result and limitations. Keep personal artifacts private; give Leo their task-local locations through the same authorized private channel. Never upload them to the public repo or open a public issue with them.
7. The cloud agent does not need to commit anything for a verification-only run. If the verifier itself needs a fix, report it rather than changing the experiment in place. No independent branch creation or main edits are authorized by this handoff.

## Checks and boundaries

The script validates archive/checksum identities; rejects missing, extra, duplicate, absolute or traversal entries; rejects special files and unsafe symlinks; preflights before extraction; compares every restored manifest entry; checks `git fsck --full --strict`, HEAD, branch/tag refs and reachable history counts; and confirms inputs/extracted files remain unchanged through verification. Git hooks and restored programs are never invoked. A non-Git folder reports Git checks as not applicable.

This first protocol supports ordinary repos with contained `.git` directories. It refuses worktree Git pointers/commondir, external object alternates, submodules, escaping/absolute symlinks and special permission bits rather than silently skipping them. Internal symlinks are preserved. Hardlink file bytes are restored as ordinary files; hardlink inode sharing is not asserted.

The comparison does not assert root-container permissions, macOS ACLs/xattrs/resource forks, ownership, timestamps, live-database consistency or application usability. Original file contents and ordinary permission bits are tested on the receiving filesystem; environment-specific mismatches must be reported. A provenance label/checksum binds the supplied baseline but cannot independently prove who captured it. Missing capture-time evidence cannot be replaced by inspecting the received archive.

## Current readiness

Harness and handoff prepared and tested with synthetic repos locally. No real personal archive or baseline has been transferred and no independent cloud restore result is claimed. The next step is provision of the agreed private inputs, followed by the cloud agent's documented run.
