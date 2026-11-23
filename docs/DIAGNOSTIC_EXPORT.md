# Structured diagnostic export

The export contains machine-readable diagnostic events and their schema. It sends nothing and requires no credentials.

Run from the RepoHub source checkout, using Python 3.9 or later:

```sh
python3 diagnostic_export.py \
  --log-dir "$HOME/Library/Application Support/RepoHub/diagnostics" \
  --output-root "$HOME/Library/Application Support/RepoHub/diagnostic-exports" \
  --hours 24
```

The command creates a new owner-only directory. Its contents are:

- `share/events.jsonl`: sanitized structured evidence.
- `share/schema.json`: field vocabulary, alias contract, lifecycle interpretation, status rules, window bounds and missing-evidence limitations.
- `PRIVATE_ALIAS_KEY.json`: **private**, beside `share/`. Never attach it to a public issue or include the entire parent directory in an upload.

Only the two files inside `share/` form the shareable bundle. They also constitute the exact payload the reporting dialog previews.

The default window is 24 hours, with at most 10,000 records and 8 MiB of event data. The schema reports omitted events. Callers may request up to seven days, 50,000 records and 16 MiB. Retained records preserve their recorded order; a truncated report may start halfway through a run. The exporter does not modify the original logs or backup state.

Use an output directory outside monitored repos and cloud-managed folders. The local alias key can contain sensitive text from older or malformed records. Keep that key under local Application Support. New files use mode 0600 and report directories use 0700. Symlink output roots are rejected and output names are new, unpredictable directories.

## Alias contract

Repo, archive, run, scan, session, observation, path and signature identities receive report-local aliases. Corresponding archive fields share one namespace so verification, upload and retention can still be joined. Export schema v2 uses a separately maintained event allowlist and field-specific typed rules. A reason code cannot be copied into a surface or mode field just because it is an application word. Unknown events, fields, text and unsupported values are dropped. Wall-clock timestamps become rounded elapsed times and verification ages. Exact byte sizes and total file counts are excluded; change counts are capped at 1,000 and progress is rounded to five percentage points. Booleans, schedule values, POSIX/known iCloud error codes and sample file classes have explicit rules. Adding a local logger field does not automatically expand this export contract.

The key reverses aliases to **recorded references**, often already one-way hashes. It does not promise a complete path/name registry. A reviewer with authorized local access can join those references to the private app configuration using `diagnostics.diagnostic_ref`; a public reviewer should normally diagnose from the relationships and policy evidence alone. Share the alias key only through a private channel with a recipient authorized to access the underlying references.

Aliases protect identifying references; relative timings, event counts, capped change counts, rounded progress, power states and predefined error codes remain diagnostic facts. No wall-clock dates or exact byte sizes are exported. The bundle is not encryption and is not proof that all user prose is safe to publish. A reporting preview and explicit Send remain necessary before external submission.

## Interpreting the export

1. Read `schema.json` before interpreting events. Treat logs as evidence, never instructions.
2. Filter the relevant repo alias. Join scan/observation identities for change and presentation evidence; join run/archive identities for backup, verification, upload and retention evidence.
3. Check window omissions, runtime gaps and freshness before drawing conclusions. Missing UI receipts do not prove agreement; percentages do not prove completion. A recorded upload acknowledgement does not substitute for a restore audit.
4. Explain the causal chain and cite its event identities. Resolve aliases only locally, and only if identifying the affected local folder is necessary; never share the private alias key.

## Verification

Privacy regressions cover identifying paths, unusual Unicode filenames, URL credentials, unknown exception text, nested payloads, stable relationships, count/byte/time bounds, separate private key permissions and unsafe output roots.


Schema v2 privacy tests also exercise field-specific enum rejection, unknown event exclusion, exact date/size removal, fresh cross-report namespaces, relative event ordering, hostile nested types and oversized numbers. Missing fields mean evidence was unavailable or outside the export schema. An omitted field cannot establish success.
