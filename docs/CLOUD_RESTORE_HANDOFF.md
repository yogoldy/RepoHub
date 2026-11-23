# Controlled receive-and-restore audit

## Purpose and exact claim

An independent verification host **receives** an archive downloaded from iCloud. It does not retrieve from iCloud, authenticate to Apple, connect a drive, or use the Mac's cached archive as a substitute. The audit covers receipt and restoration of the supplied archive. Direct retrieval from iCloud requires a separate check.

A pass means: **the supplied archive matches the trusted expected archive checksum and restores to the supplied independently captured source baseline, with contained Git integrity/history checks passing where applicable.** It does not prove Apple provenance, future backups, every repository, or that the restored application runs.

## Pin and disclose the controls

| Variable | Control/evidence |
| --- | --- |
| Verifier source | Pin the verifier to the exact commit selected for the audit; record `git rev-parse HEAD` and `git status --porcelain` before starting. Do not silently update the verifier. |
| Archive identity | Exact expected SHA-256 taken from the app's recorded backup receipt, not recomputed from the received archive to create the expectation. |
| Source expectation | `expected.json` captured by the local source-inventory command; it must describe the same content point in time as the chosen backup. Never derive it from the tested archive. |
| Baseline transfer | Expected SHA-256 of `expected.json` supplied separately in the trusted handoff. The tool checks it before parsing. |
| Download provenance | User records archive identity, download method/date and whether it came from iCloud.com. The verifier cannot authenticate that statement. |
| Restore destination | New private directory per run; existing outputs are refused. Never restore over a working repo. |
| Toolchain | Python standard library and installed Git; log versions, platform, verifier-file hash, Git subcommands, exit codes and output digests. No dependency install is needed. |
| Execution/network | Do not execute restored code or hooks, run its tests, install its dependencies, contact remotes, or change global Git/system config. Git commands explicitly disable hooks, fsmonitor, lazy fetch, prompts and set Git’s default transport policy to `never`. Enforce offline execution with the receiving environment’s network controls. Cloud egress should be disabled after the inputs arrive; document the actual environment network setting. The script itself is not an OS network sandbox. |
| Limits | 250,000 entries, 128 MiB baseline JSON and 120-second Git-command timeout remain. No fixed compressed/expanded byte ceiling. Optional `--max-bytes` bounds total restored regular-file bytes. Destination capacity must cover remaining data, per-entry allocation allowance and a configurable free-space reserve (512 MiB by default). Insufficient capacity is a failed run, not a pass. |
| Immutable inputs | Record the initial input hashes and recompute both at the end to check for changes and check source/input changes during capture/verification. Do not edit or regenerate inputs to make a failure pass. |
| Deviations | Record every departure from the handoff before the test. Missing inputs or unsupported cases stop the test; disclose them. |

Record the controlled variables and any known sources of uncertainty. OS/filesystem/tool behavior remains part of the recorded test environment.

## Local source-baseline preparation

This runs on the Mac that made the backup, **not on the receiving computer**. Select a particular backup receipt and its repo. The source must still represent that backup's content point in time. If it has changed, do not manufacture a historical baseline from the archive: choose an unchanged repo or coordinate a new backup and independent capture while editing is paused. By default, Finder-only differences are real differences for this audit. RepoHub deliberately keeps the existing archive when only `.DS_Store` files change, so the strict comparison fails for as long as those Finder files differ from the archive. For that case, `verify --allow-finder-only` lets regular files named `.DS_Store` outside `.git` differ (changed, added or removed). They are restored from the checksum-verified archive, the receipt counts each kind under `finder_only_differences`, and every other entry, including `._*` files and anything in `.git`, must still match exactly. The one Finder allowance is in Git's strict check: Finder can leave `.DS_Store` or `._*` files inside `.git/refs`, which `git fsck --strict` reports as bad references. The verifier accepts that only when fsck reports reference errors alone and every one names such a Finder file; the files are still restored and compared byte for byte, and any other fsck error fails.

Choose a new private directory outside monitored repos, the source folder and the tracked checkout. Capture all regular-file bytes, permissions, directories and symlink targets, including `.git`, ignored files and uncommitted files:

```sh
python3 -B restore_audit.py capture \
  --source '<absolute-local-source-repo>' \
  --archive-sha256 '<trusted-SHA256-from-backup-receipt>' \
  --out '<new-private-baseline-directory>'
```

`expected.json` and its checksum in `result.json` are the handoff baseline. The source is checked for changes while capturing, including after read-only Git checks. Capture success is not restore success and does not establish that an older archive matches the current source. Record the receipt's backup time separately from the baseline capture time.

## Required inputs for the verification host

1. The actual `.tar.gz` backup downloaded from iCloud, transferred privately to the verification host.
2. `expected.json`, independently captured from the matching live source.
3. Its trusted SHA-256, sent separately from the file.
4. A brief user provenance statement and the expected source/backup time-point alignment.

For the audit, the public repository supplies the verifier, tests and instructions. The archive and matching source baseline must be supplied privately. A GitHub clone is not a substitute for the backup. Never commit/archive private inputs, manifests, extracted trees or logs in Git; keep them outside the checkout. They may contain secrets and private filenames. Do not put secrets or public download URLs in issues or a publicly distributed filesystem image. Transfer private audit inputs only by a method authorized by the data owner.

## Run the independent verification

1. Confirm the pinned verifier revision is checked out and unchanged. Keep the verifier revision and command transcript in the private audit record outside Git. Confirm the three required verification inputs actually exist; if any are missing, record them and stop. Verification requires no iCloud credentials.
2. You may run synthetic tests first. Record them separately and label them **synthetic harness validation**, separately from verification of an archive received from iCloud:

   ```sh
   python3 -B -m unittest discover -s tests -p 'test_restore*.py' -v
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

5. Save the command, exit code, exact verifier Git revision and input-transfer/provenance statement in the private audit record. The tool produces private `events.jsonl`, `result.json`, and the isolated `restored/` tree. Logs record stages, versions, identities, durations and Git command return codes/output digests; they do not print file contents or raw Git outputs. A missing result or nonzero exit is not a pass. Do not modify the archive, expectations or verifier and rerun silently; any revised experiment needs a new output directory and disclosed rationale.
6. Report the archive checksum, manifest checksum, entry count, Git verified/not-applicable result, final result and limitations. Keep personal artifacts private and out of the repository. Never upload them to the public repo or open a public issue with them.
7. Run verification against the pinned revision. Record verifier defects separately and use a new audit record when testing a fix.

## Checks and boundaries

The script validates archive/checksum identities; rejects missing, extra, duplicate, absolute or traversal entries; rejects special files and unsafe symlinks; preflights before extraction; compares every restored manifest entry; checks `git fsck --full --strict`, HEAD, branch/tag refs and reachable history counts; and confirms inputs/extracted files remain unchanged through verification. Git hooks and restored programs are never invoked. A non-Git folder reports Git checks as not applicable.

This protocol supports ordinary repos with contained `.git` directories and standard registered-worktree administrative files whose `commondir` is the relative internal shared-store reference `../..`. Administrative files must be regular, bounded and hash-consistent; malformed or redirected stores fail before Git checks. Original checkout back-pointers are retained as bytes and are not followed to capture outside checkout contents. Receipts disclose the registration count and `linked_checkout_contents_verified: false`. Root linked-worktree `.git` files, external object alternates, submodules (a top-level `.gitmodules`; copies deeper in the tree, such as inside `node_modules` packages, are ordinary files), links inside `.git` with absolute or lexically escaping target text and special permission bits remain refused rather than silently skipped. One exception matches what the app backs up: an empty `.git` file below the top level, such as a `uv` cache marker, cannot point anywhere, so it restores and is compared byte for byte like any other file. A worktree checked out in a folder inside the repo, for example under `.tools/worktrees/`, is also supported: its files are already in the archive and compared byte for byte. Capture accepts its `.git` pointer file only when it names a worktree registered in this same repo and that registration names the file back (absolute paths must point at the source itself; relative paths must stay inside). Capture records each pairing in `expected.json`, verify refuses any pointer file the baseline does not pair before extracting, rechecks the pairing after restoring, and the receipt reports `checkouts_inside_repo`. Any other non-empty nested `.git` file and a top-level `.git` file are still refused. Other links that leave the repo, such as a linked `node_modules` folder or a virtual environment's interpreter link, restore as the same link text. Capture follows them for a target-type metadata check only, without reading their target contents into the archive. Capture and restore receipts list each one with its scope and observed target type, and list the supplied separate-archive checksums under `included_archives`. The aggregate `contents_included` flag is true only when every listed link has an inclusion record. Each separate archive still needs its own audit. RepoHub saves an included linked folder as its own verified archive beside the repo backup; pass `--include LINK=SHA256` to `capture` to name that archive in the receipt, and audit the folder archive with its own capture and verify run. The audit leaves restored folder contents in the output directory. Returning them to their original location is a separate operation. Included linked checkouts are saved the same way; pass `--checkout NAME=SHA256` to `capture` to name each checkout archive by its Git registration. The audit refuses a checkout archive on its own because its root `.git` is a file; reattaching a restored checkout with Git is a separate operation. The supported metadata layout follows [Git’s repository layout documentation](https://git-scm.com/docs/gitrepository-layout). Internal symlinks are preserved. Hardlink file bytes are restored as ordinary files; hardlink inode sharing is not asserted.

The comparison does not assert root-container permissions, macOS ACLs/xattrs/resource forks, ownership, timestamps, live-database consistency or application usability. Original file contents and ordinary permission bits are tested on the receiving filesystem; environment-specific mismatches must be reported. A provenance label/checksum binds the supplied baseline but cannot independently prove who captured it. Missing capture-time evidence cannot be replaced by inspecting the received archive.

## Large restores and capacity evidence

`verify` plans capacity on the filesystem containing its new output directory,
before hashing a potentially cloud-backed archive or creating the restored tree.
It repeats the check before extraction, at entry boundaries and during file copies.
Archive hashing and regular-file restoration stream data in chunks of at most 1 MiB. The verifier reads the size-limited baseline JSON into memory. The receiver must already have room
for the supplied archive; allocation planning covers the additional restored data,
per-entry allocation allowance and reserve. These checks do not reserve space or
guarantee future availability against other writers or filesystem quotas.

Optional flags are explicit byte counts:

- `capture --max-bytes N` and `verify --max-bytes N` reject manifests whose total
  regular-file sizes exceed N. Omitting this flag applies no fixed byte ceiling.
- `verify --reserve-bytes N` changes the extra free-space reserve; the default is
  536870912 bytes (512 MiB). Zero is allowed only when deliberately requested.

`restore_capacity` events record numeric free/required/remaining bytes and reserve,
without private source paths. `restore_capacity_insufficient` identifies a failed
capacity check; `restore_capacity_exhausted` identifies an OS out-of-space/quota
failure. Failed partial output stays in its private run directory for inspection;
archives and baselines are never deleted or changed to recover space. Use a new
output directory for a disclosed retry.

The checked-in tests do not establish whether a local checkpoint restored an actual 8 GiB plus 1 MiB
fixture, compared the full manifest, rechecked both inputs and cleaned only its
owned temporary data. Recovery tests also exercise above-8-GiB planning, explicit
budgets, low disk, mid-copy space loss and bounded-memory streams. These synthetic
results do not establish a restore of a very large real repository on a receiving Mac with limited free space.

## Verification coverage

The verifier has local synthetic coverage for contained registered-worktree metadata and capacity-aware large restores. A cross-device restore result applies only to the repositories identified in its receipts and transfer records. Direct retrieval from iCloud requires separate verification. `--include` and `--checkout` record references to separate archives. They do not capture those archives’ contents or verify their supplied checksums.
