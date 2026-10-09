# Bug and feature report previews

Open the main settings gear, then choose **Report a glitch** or **Request a feature**.

Glitches ask for a title, what happened and what was expected. Sanitized diagnostics are selected by default; choose the last hour, day or week, or remove them. Feature requests ask what the user wants and why, with diagnostics off by default. The two flows retain separate in-memory forms during the current page session.

**Preview report** creates a private local draft and displays the proposed public destination, prose, category labels and diagnostic files. Text is rendered with `textContent`, not interpreted as HTML. Expand a file to inspect its complete content. **Edit report** returns to the form, where diagnostics can be removed before generating another preview. Closing the dialog keeps its fields in memory. A failed request keeps the prose visible and allows retry after the helper returns.

The backend stores drafts in local Application Support `reports/<report-id>/draft.json`, separate from monitored repos and saved workspace data. The response contains only the shareable diagnostic files, never the sibling private alias key. Report files are owner-only. Diagnostic attachments are bounded to 1,000 events and 1 MiB of event data; the schema separately describes omissions and the event window.

This is a preview implementation. **Send to GitHub is disabled**, nothing is submitted and no credentials are accessed. GitHub authentication, the supported attachment mechanism, final submission, delivery receipts, duplicate prevention and reopening stored drafts after a restart belong to Tiers 2C/2D. Current file previews are proposed attachments, not a claim that GitHub offers a general attachment-upload API. Typed prose is shown verbatim and can contain private information; the public disclosure therefore applies to prose as well as diagnostic files.

## Verification

The full suite has 118 passing Python tests on both Macs. New checks cover required fields, bug/feature categorization, optional diagnostics, private-key exclusion, exact stored preview equality, file permissions, invalid inputs and the existing HTTP Host/Origin/token boundary. JavaScript status and delivery checks pass, the new script parses, and the native macOS 13 target compiles after updating installer packaging.

A live local browser check exercised glitch and feature previews, default diagnostic choices, removing diagnostics, editing a preview and an interrupted-helper failure followed by successful retry with the same prose. The preview remains available on an isolated staging helper; it has not replaced the stable installed app. Separate private Air dogfooding constructed a report from real helper logs and reviewed only its shareable files. Concrete private report contents and diagnostics remain outside Git.

Report previews use diagnostic export schema v2: only explicitly typed facts are included. Diagnostic files contain no wall-clock dates or exact byte sizes; they retain report-local aliases, relative timings and bounded operational measurements. User-authored title and prose remain separate and are accompanied by “Please don’t send any confidential information.”
