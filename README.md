# RepoHub

RepoHub is a small Mac menu-bar app that keeps verified backups of your code folders in iCloud Drive and tells you, honestly, whether they are safe.

RepoHub distinguishes finishing a local copy from confirming its upload. RepoHub only shows a green check when **both** of these are true:

1. **The copy is verified.** RepoHub hashes the files in your folder and checks their contents against the saved archive, then repeats that check regularly. The comparison covers regular files, directories and symlink targets, including `.git`, uncommitted changes, ignored files and dependencies. It skips sockets and named pipes. The one deliberate exception is Finder's `.DS_Store` view-settings files: Finder rewrites them constantly, so a difference in them alone doesn't trigger a new backup (the card's details say when that applies).
2. **macOS confirms the upload.** The archive has been uploaded to iCloud, as reported by macOS itself. When upload status determines the card, missing upload evidence shows “Upload status unavailable.” Stale checks show “Waiting for fresh checks.”

The backup copier reads your source folders. Git status checks can also run filters configured for your user account or system.

## What it does

- Watches the folders you choose (every 30 seconds) and backs them up on a schedule you set, or after you stop editing.
- Saves each folder as one `.tar.gz` archive in a backup folder you choose in iCloud Drive.
- Keeps the previous archive until the current repo archive and all included linked-folder or checkout archives have confirmed uploads and pass checksum verification, then removes superseded managed copies.
- Shows each folder's state in a card in the menu bar: backed up, backing up, waiting for iCloud, changed, or needs attention.
- After setup, RepoHub attempts login registration once if needed. Backups resume at login when macOS enables the item or an existing launch agent starts the app. It also checks for updates and asks before installing one.
- RepoHub has to be running to back up: **Quit** stops backups until you open it again.

## What you need

- A Mac with Apple silicon (M1 or newer). Intel Macs are not supported.
- macOS 13 (Ventura) or later.
- iCloud Drive turned on, and enough iCloud storage for your backups.

## Get started

1. Download the latest `RepoHub-<version>-arm64.zip` from the [Releases page](https://github.com/yogoldy/RepoHub/releases/latest) and unzip it.
2. Drag **Repo Hub.app** into your **Applications** folder and open it.
3. Follow the five-step setup that appears in the menu-bar panel: choose what to back up, choose where backups go, check access, choose a schedule, review.

The full walkthrough, including the permissions macOS will ask for, is in the [getting started guide](docs/GETTING_STARTED.md). If something looks wrong, see [troubleshooting](docs/TROUBLESHOOTING.md).

## Restoring a backup

Backups are ordinary archives. To restore, download the archive from iCloud, check its checksum against RepoHub's record, and extract it into a **new, empty folder**. Never extract over a working folder. The [getting started guide](docs/GETTING_STARTED.md#restore-a-backup) has the exact steps.

## Limits worth knowing

- **Only the newest backup is kept.** RepoHub is a safety copy, not a version history. Committed history stored inside the selected folder is included (a linked Git checkout stored elsewhere is saved only if you choose to include it, as its own archive; see the restore steps), but older versions of uncommitted or ignored files are replaced.
- **It saves everything in each folder you choose,** including ignored files such as `.env` files and keys, and has no exclusion list yet (sockets and named pipes are skipped, and other unsupported special files stop the backup). Archives rely on iCloud's own protection.
- **Not a snapshot of a running database or open document.** RepoHub reads live files. Close databases and workbooks before backup to reduce the chance of capturing an inconsistent application state.
- **iCloud only for now.** Other sync folders are on the roadmap, not supported yet.
- **Symlinks that point outside a folder are saved as links, not followed.** After setup you can include an outside linked folder as its own verified archive from that repo's card.
- **Upload confirmation is macOS's word, not an independent audit.** To verify that the downloaded bytes match the recorded archive, download it on a second Mac and compare its checksum, as described in the guide.

## Privacy

RepoHub runs entirely on your Mac. Its helper listens only on `127.0.0.1`. RepoHub’s built-in external service endpoints are on GitHub: update checks and downloads, plus account checks, issue submission and delivery checks when you use GitHub reporting. A bug report is posted only when you choose Send to GitHub or Retry send, and only the exact preview you approved goes out, as a public GitHub issue. Raw diagnostics and their private alias key stay on your Mac, and there is no telemetry; if you include diagnostics in a report, the selected sanitized excerpts become public when you press Send. Your **backups**, including any credentials inside the folders you choose, do leave your Mac: macOS uploads them to your iCloud Drive, so choose folders accordingly.

## For contributors and curious people

- [How RepoHub works](docs/HOW_IT_WORKS.md): the detailed technical reference.
- [Contributing](CONTRIBUTING.md): build, test and propose changes.
- [Security](SECURITY.md): how to report a vulnerability.
- [Roadmap](ROADMAP.md).

## License

RepoHub is released under the [MIT License](LICENSE). The app bundles other open-source components (Sparkle and a standalone Python), which keep their own licenses.
