# Verification — 2026-10-09

## Current behavior

- Twelve synthetic unittest checks pass. Retention checks cover verified replacement, unchanged skip, failure preserving the older copy, corrupt retained archives preventing cleanup, index-publication failure/retry, and cleanup confinement to app-managed archive names and folders. Archive checks include Git internals, ignored files, symlinks, source-change rejection, and metadata-display filtering. Existing JSON persistence, conflict checks, scoped paths, origin/Host checks, and app-data backup are also exercised.
- The installed native app opens directly to the status list: no sidebar, navigation, notes editor, or Repo views screen. Advanced is off by default; it retains staged/unstaged/untracked counts and archive details.
- Installed configuration is `retention: latest`. A successful live run retained exactly one archive in each of the eleven repo snapshot folders and one for saved helper data; all eleven repos matched with no backup errors. Both helper and menu-bar login jobs remain installed.
- Replacement copies include Git history and ignored/uncommitted files. Copy/checksum/index-publication failure preserves older archives. Superseded managed archives are removed only after verifying the retained copy.
- The native binary and app packaging retain the previously verified macOS 13 minimum. No Swift or packaging code changed in this task.

## Preserved data and limits

Legacy Current repos and Desktop repos Previous Versions were deliberately left intact. Existing saved JSON and backend view/data APIs were preserved despite removal of their UI. Source repos other than RepoHub were not edited, cleaned, or committed. Native recompilation and another HTML-notes UI round trip were skipped because neither is part of the current change; JSON APIs were tested. No logout/reboot or iCloud server-side upload check was performed. Matching uses source metadata and a locally verified archive; see README for live-copy and metadata-detection limits. Older uncommitted/ignored-file versions disappear when their superseded managed snapshot is removed.
