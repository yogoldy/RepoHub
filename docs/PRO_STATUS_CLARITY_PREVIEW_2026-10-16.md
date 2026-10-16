# Pro-only status-clarity test installation — October 16, 2026

## Authorization and installed version

Leo explicitly requested installation on the MacBook Pro so he could test the
changes, then confirmed the Pro-only preview scope. This is a test installation,
not full release acceptance or a waiver for future releases. Main was not moved,
no PR was merged, and the Air was not contacted or changed.

Installed application source: `8d8de3b68d5e3a98df4d4c2602de7cd3c9c3f4b5`.
The clean macOS Golden Gate for this exact application source passed 208 Python
tests, zero skips, all 19 rules, and all 20 JavaScript/native commands. Browser
acceptance covered 13 controlled situations with no presentation disagreements.
This documentation commit does not alter that application payload.

## Deployment and preservation evidence

The personal migration installer was deliberately not run. A verified package
from the gate supplied the runtime and compiled binaries. The existing daily
bundle identity and configuration paths were retained; the helper registration
now uses the tested native launcher with its original interpreter/configuration.
All installed runtime files matched the payload. Native executable code matched
after removing ad-hoc signatures from disposable comparison copies; the installed
bundle was separately signature-verified. Bundle metadata records the source SHA.

Private persistent rollback copies retain the previous app, runtime, launch
plists, configuration, data registry and preferences. An independent watchdog was
ready before the jobs were stopped. Successful installation was confirmed only
after preservation and helper/UI checks. The preview did not edit source repos or
backup destinations. Existing automatic scheduling remained enabled.

All 13 workspace IDs, paths and active selections were preserved. Configuration,
default settings and per-repo schedule bytes matched their captured baseline.
The new registry initialized directory identity evidence for the repo home and
13 sources. A normal scheduled backup completed during observation; the helper
reported no repo/backup errors. Current-session presentation diagnostics reported
zero disagreements with policy `status-clarity-1`.

## Guarded first attempt and recovery

The first deployment guard accepted identity additions to workspace entries but
incorrectly compared the repo-home source record byte-for-byte. It rejected the
expected new identity evidence and restored the old binaries. The old runtime
then rejected the newer registry's identity fields. This was a deployment guard
and rollback compatibility finding, not lost or changed monitoring selections.

Inspection proved every original registry field was unchanged and only identity
evidence had been added. Restoring the exact original registry recovered the old
helper and its 13 sources. The corrected guard checks every original field and
allows only the intended new identity field. Rollback now restores the matching
old registry only when this same bounded migration is the sole change; unexpected
selection changes are preserved for review rather than discarded. The second
installation passed these guards. A permanent automated downgrade/rollback
regression remains future release-tooling work; this record is not such a test.

## Native smoke evidence and limits

Computer use observed first-launch readiness/settings in the installed app,
then the updated repo menu, information button, complete status explanations,
and Show me returning to the selected repo. The menu displayed actual archive
creation and subsequent upload activity from its normal schedule.

Additional native technical-disclosure/report clicks were not accepted as passed:
AX activation of the summary control was unsupported, and repeated automation
attempts lost the transient popover window. These tool/control observations do
not establish that the app hung. Browser reporting/keyboard/technical-disclosure
checks remain browser evidence, not substitutes for installed native acceptance.
No real report was sent and no credentials or macOS privacy permissions were reset.

The [full native two-Mac backlog](MAIN_INTEGRATION_EXCEPTION_2026-10-16.md) stays
open, including permissions, faults, volumes, notifications and final-candidate
interaction/restart checks. Leo can now exercise this installed Pro test version.
The tutorial and deeper failure investigation remain future work.

## Private rollback records

Persistent records are under the Pro's RepoHub application-support rollback
folder, with owned run names `pro-preview-20261016-8d8de3b` and
`pro-preview-20261016-8d8de3b-retry2`. The second run has the successful installed,
confirmation and preservation receipts plus its guarded restore script. Raw logs,
source paths, registry contents, hashes and preferences stay outside Git. Review
current selections and backup activity before a later rollback; do not blindly
replace user data changed after this checkpoint.
