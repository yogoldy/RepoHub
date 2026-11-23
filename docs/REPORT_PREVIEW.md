# Bug and feature report previews

Open the main settings gear, then choose **Report a glitch** or **Request a feature**.

Glitches ask for a title, what happened and what was expected. Sanitized diagnostics are selected by default; choose the last hour, day or week, or remove them. Feature requests ask what the user wants and why, with diagnostics off by default. The two flows retain separate in-memory forms during the current page session.

**Preview report** creates a private local draft and displays the proposed public destination, prose, category labels and diagnostic files. Text is rendered with `textContent`, not interpreted as HTML. Expand a file to inspect its complete content. **Edit report** returns to the form, where diagnostics can be removed before generating another preview. Closing the dialog keeps its fields in memory. Reopen a saved report loads a persisted preview/receipt after page or helper restart. A failed request keeps the prose visible and allows retry after the helper returns.

The backend stores drafts in local Application Support `reports/<report-id>/draft.json`, separate from monitored repos and saved workspace data. The response contains only the shareable diagnostic files, never the sibling private alias key. Report files are owner-only. Diagnostic attachments are bounded to 100 events and 20,000 bytes of event data, with the total posted body limited to 60,000 UTF-8 bytes; the schema separately describes omissions and the event window.

Delivery is explicit, through [the delivery contract](REPORT_DELIVERY.md): credentials remain in native Keychain, diagnostic files become bounded text blocks in the exact issue body, and Send uses a durable receipt/reconciliation workflow. There is no arbitrary attachment-upload API. User prose is shown verbatim and can contain private information.

## Preview test coverage

The test suite's checks cover required fields, bug/feature categorization, optional diagnostics, private-key exclusion, exact stored preview equality, file permissions, invalid inputs and the existing HTTP Host/Origin/token boundary. Additional checks cover JavaScript status and delivery, script syntax, and compilation of the packaged macOS 13 target.

Browser verification covers glitch and feature previews, default diagnostic choices, removing diagnostics, editing a preview and an interrupted-helper failure followed by successful retry with the same prose.

Report previews use diagnostic export schema v2: only explicitly typed facts are included. Diagnostic files contain no wall-clock dates or exact byte sizes; they retain report-local aliases, relative timings and bounded operational measurements. User-authored title and prose remain separate and are accompanied by “Please don’t send any confidential information.”
