# Explicit GitHub report delivery

The source now implements Tiers 2C/2D; the installed stable release remains preview-only until this branch is merged and deployed. Reports target only `yogoldy/RepoHub` public issues. Nothing sends in the background or merely because a preview, connection check or app restart occurs.

## Connection and consent

In the native menu bar, expand Things to know and choose GitHub reporting connection. The native secure text field saves a user-supplied GitHub token in macOS Keychain under `com.leogoldberg.repohub.github` / `github.com`, or removes it on Disconnect. It never accepts a token, URL or command from JavaScript. The helper reads that specific record through Apple's security utility; credentials exist only in native/backend memory and request headers, never app files, HTML, logs or Git. System Keychain access prompts may require user approval. Keep each Mac's connection separate.

For the tracker owner, a fine-grained token selected for RepoHub with Issues read/write is supported. GitHub currently limits fine-grained tokens for public contributions outside the user's membership; those users need a classic `public_repo` token for this initial adapter, which grants broader public-repository access. The native dialog discloses that tradeoff. A smoother registered GitHub App/OAuth connection is future work, not a hidden use of Leo's credential. See [GitHub's token documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

The preview checks the current GitHub account and displays who will author the issue. Send confirms the displayed report ID, exact payload digest and account. A changed account or stale/changed preview cannot silently publish. Connection checks are authenticated reads, not writes. No credentials are submitted through the loopback report APIs.

## Exact public payload

The prefixed title (`[Bug]` / `[Feature]`), prose, random report ID, report type and optional diagnostic text blocks form the public issue. Files are embedded as fenced JSON text, not separately uploaded attachments. The preview shows the complete exact body and also convenient file inspection views. A bug defaults to diagnostics; a feature defaults to none. The confidentiality reminder stays visible.

Shareable logs use the explicit typed export contract, at most 100 events and 20,000 bytes of event data; the schema describes omissions. Total issue-body size is capped conservatively at 60,000 UTF-8 bytes. An oversized report fails before POST and remains editable. Private alias keys, source files and archives are never included.

`bug` versus `enhancement` and the common `from-app` label are requested. GitHub can ignore label requests from non-maintainers; the owner-side Categorize app reports workflow applies only fixed labels to newly opened matching reports. It parses issue JSON, validates tracker/number/type markers and never interpolates prose into commands. It activates only on main after merge. Titles/type markers keep reports distinct while labels are pending. The common label has been created in the product tracker.

## Durable delivery states

| State | Meaning | Next user action |
| --- | --- | --- |
| Draft | Preview stored; no POST attempted. | Review and Send. |
| Sending | Durable intent recorded before POST. | Wait; another click cannot start a concurrent POST. |
| Sent | Exact title/body/author/tracker/issue number confirmed. | Open the saved issue URL; repeat Send returns this receipt. |
| Failed | Authentication, account mismatch or explicit GitHub rejection. | Fix connection/permissions, then deliberately retry the same draft. |
| Uncertain | POST/response may have succeeded, or helper restarted after sending intent. | Check delivery; never blindly repost. |

An owner-only `delivery.json` accompanies the immutable preview; a process-safe per-report lock serializes Send. Preview and receipt writes flush file data and directory entries; a failed sending-intent flush cannot start POST. Interrupted `sending` becomes uncertain. Reconciliation lists up to 2,000 authored issues in all states and requires exact title/body, report marker, author and tracker identity. It uses the issue list rather than indexed search, but list visibility can also lag creation. No match, a modified issue or a failed read is not proof that a prior POST failed. The state stays uncertain; recovery may need manual investigation. There is deliberately no automatic resend/override that can create duplicates.

The UI preserves separate bug/feature text and reopens the latest 25 saved reports. Older previews lacking exact-payload metadata must be reviewed as a new preview; their stored body is available as editable text. Sent/uncertain reports cannot be edited into a second issue under the same identity.

## Diagnostic and test evidence

`report_delivery` records only a report reference, approved state and reason code. Export aliases the reference; account names, titles, prose, issue URLs, raw errors and credentials are excluded. Credential changes are not reflected into logs. Logging failure does not prevent a legitimate report send.

Regressions cover exact receipts, lost response, crash, ambiguous absence, explicit rejection, concurrent double-click, account/preview changes, path/consent/destination injection, foreign receipts, bounds, private-key exclusion, diagnostic sanitization and the existing Host/Origin/token boundary. Fixed-label routing treats issue text as untrusted data. Golden rule GR13 binds the safety requirements to actual executed tests.

An isolated browser harness simulates Send to exercise timeout → Check delivery → confirmed receipt and reopening after page reload; its banner explicitly says no issue is posted. Real API acceptance uses a private disposable tracker and synthetic prose/diagnostics, verifies exact returned bodies/labels and one issue per report after repeat Send. GitHub's issue list can lag its creation response; the harness polls reads without retrying POST. No fake report is sent to the public product tracker. Concrete test receipts stay outside Git.

Native builds/bridge tests validate compilation and fixed-action origin restrictions. Real user credential entry, Keychain access prompts and installed connection setup on both Macs still require live acceptance. Credentials were not automatically migrated from the developer CLI into the app. Deployment, OAuth onboarding and maintainer review automation are separate work.
