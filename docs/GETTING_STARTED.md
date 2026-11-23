# Getting started with RepoHub

This guide takes you from download to your first verified backup, and shows how to read the menu-bar panel and restore a backup. For a quick overview, see the [README](../README.md). If something doesn't look right, see [troubleshooting](TROUBLESHOOTING.md).

## Before you begin

- A Mac with Apple silicon (M1 or newer) running macOS 13 or later.
- iCloud Drive turned on (System Settings → your name → iCloud → Drive) with enough storage for your backups.
- **Space.** A backup is one compressed archive per folder, whose size depends on how well its contents compress (its `.git`, dependencies and ignored files included). RepoHub keeps the previous archive of a folder until the new one is confirmed uploaded, so plan for about twice your total folder size during an ordinary update, on your Mac's disk and in iCloud. If uploads fall behind (you're offline, or iCloud is full), newer archives can pile up until macOS confirms one. Setup checks free space on your Mac and refuses a destination that is too full. It can't see your iCloud plan, so look at System Settings → iCloud: compare the available iCloud storage with the size of your projects and any archives still awaiting upload, and you may need a paid plan.
- **Privacy of what is saved.** A backup contains **everything** in each folder (hidden files, ignored files and dependencies; sockets and named pipes are skipped, and other unsupported special files stop the backup), including ignored files such as `.env` files, private keys and credentials. RepoHub has no exclusion list yet, and archives are protected only by iCloud's own protection. Don't back up a folder you wouldn't want in iCloud.

## Install

1. Download `RepoHub-<version>-arm64.zip` from the [latest release](https://github.com/yogoldy/RepoHub/releases/latest) and double-click it to unzip.
2. Drag **Repo Hub.app** into your **Applications** folder.
3. Open it. RepoHub is signed with a Developer ID and notarized by Apple, so macOS may ask you to confirm that you want to open an app downloaded from the internet. If it does, click **Open**.

RepoHub has no Dock icon. Look for its icon in the right side of the menu bar. Click it to open the panel.

## First-run setup

A five-step setup opens in the panel the first time. Nothing is backed up until you finish it.

1. **What would you like to back up?** Choose Repo-home folder or Individual folders. Individual folders also offers Git discovery.
   - **Repo-home folder:** RepoHub watches **every visible folder directly inside it** (for example everything in `~/Developer`), including folders that aren't Git repos. Repo-home skips hidden folders and symlinked children. In Individual folders, you can select a hidden folder or monitor a linked folder’s resolved target, and note that switching modes stops automatic discovery of new folders. Pick this mode if all your projects live in one place.
   - **Individual folders:** choose folders at different places.
   - **Find Git repos:** scan a folder using installed Git, then tick the eligible repositories. Discovery shows skipped areas and disables repos whose Git storage is outside the folder.

   You review the exact list before anything is saved.
2. **Where should backups go?** Choose one folder in iCloud Drive (for example a folder called `Repository Backups`). RepoHub keeps a subfolder per repo inside it and checks that the folder really is in iCloud Drive and that it can write to it.
3. **Check folder access.** macOS protects some folders (Desktop, Documents, Downloads and external drives). RepoHub reads each folder you chose to find out whether it is allowed, and reports the first access or layout error it encounters. An access error can have several causes. See [permissions](#permissions).
4. **Choose your backup schedule.** Separate choices for when your Mac is on battery and when it's plugged in: every 15 minutes up to every 4 hours, with an independent option to back up after edits settle. Turn both triggers off for manual-only operation. The defaults are hourly on both and no after-edit backups.
5. **Ready to finish?** Review everything, then **Finish and back up now**.

**Your first backup.** Find your folder's card in the panel. While it copies you'll see the circular arrow. After verification, the card can show Uploading, a question mark while confirmation is pending or unavailable, or a green check if macOS has already confirmed the upload. A question mark means *the local copy is made, but macOS hasn't confirmed the upload yet (or RepoHub can't confirm everything about it)*, and the card changes when RepoHub receives fresh evidence from macOS. If a card stays on the question mark much longer, see [troubleshooting](TROUBLESHOOTING.md#a-folder-says-awaiting-upload-confirmation-or-uploading-for-a-long-time).

You can reopen setup later from **Settings → Welcome & backup setup** to change folders, the destination or the schedule. Changing the destination never deletes archives already in the old location.

**Linked folders.** If a folder contains links to folders outside it (for example a `node_modules` kept elsewhere), RepoHub saves the link itself, not what it points to. After setup, open that repo’s card and choose **Outside this folder**. Under **Linked folders**, choose **Include contents** for each eligible folder, then **Save changes**. The next backup of that repo creates or verifies its separate archives.

After setup finishes, RepoHub attempts login registration once if needed. Check the reported login state to confirm that backups will resume at login. If macOS asks for approval, approve it in System Settings → General → Login Items & Extensions. **Settings → Access & permissions** shows the current state. Turn it off in System Settings at any time; Once RepoHub has made its registration attempt, it will respect a later switch-off.

## Permissions

RepoHub asks macOS for as little as possible:

- **Files & Folders (required for the folders you choose).** Reading a protected location such as Desktop or Documents can trigger a macOS permission prompt. Click **Allow**. If you clicked Don't Allow, open **Settings → Access & permissions** in the panel and choose **Folder privacy settings** (it opens System Settings), switch RepoHub on, and run **Check access** again. Without permission, RepoHub can't read that folder and says so; it never backs up a partial copy.
- **Notifications (optional).** RepoHub can tell you when a backup is complete and is uploaded, or when a problem lasts. Refusing doesn't stop backups.
- **Login Items (registration attempted automatically when needed).** See above.

RepoHub never asks for Full Disk Access or Accessibility.

## Reading the panel

The panel shows your folders as cards. Click one to see details. The icons:

| Icon | Meaning |
|---|---|
| Check mark | **Backed up**: contents verified and macOS confirmed the upload of the current archive. Also shown when only Finder's `.DS_Store` files differ; the card's details then say so |
| Page | **A backup is waiting to run** (first backup pending, edits found since the last backup, or only Git data or file metadata changed). Waiting for a scheduled backup is normal |
| Circular arrow | **RepoHub or macOS is working**: scanning, creating the backup, or uploading to iCloud. A progress bar reaching 100% does not confirm the upload |
| Question mark | **Upload not yet confirmed**: the local backup exists, but macOS hasn't confirmed the upload, or can't say. RepoHub never turns "unknown" into a green check |
| "!" in a circle | **Waiting for fresh checks**: the information is outdated, so RepoHub won't show green |
| Warning triangle | **Needs attention**: a copy or upload problem |

The panel's **What your backup status means** page (under the information button) explains each label in the app.

A card is green only with **verified contents and a macOS-confirmed upload of the same archive, checked recently**. An active upload shows the working icon. Pending or unavailable upload confirmation shows a question mark when no higher-priority status applies.

**Quit stops backups.** The helper that makes backups runs as a child process managed by the installed app and finishes any in-flight backup before stopping, so quitting the app stops it, and no backups happen until you open RepoHub again or an enabled login item or launch agent starts it. Leave it running; its controls are in the menu bar, and it has no Dock icon.

Useful buttons: **Back up…** and **Rescan…** in the overview, or **Back up [repo name]** and **Rescan [repo name]** in details (in a repo's expanded details they back up or rescan that repo; in the overview they let you choose repos; Rescan looks for changes without making a backup), the folder icon on a card (shows the folder in Finder), **Repository Backups** (opens your backup folder), and **Settings**.

## Where things are stored

- **Your backups:** in the backup folder you chose, one subfolder per repo, each holding `<date>.tar.gz`. Only the newest archive of each folder is kept, once it is verified and uploaded.
- **RepoHub's own data:** `~/Library/Application Support/RepoHub` (settings, status, logs). It also backs up its helper data to iCloud, including settings, the workspace registry, saved workspace JSON and its revision history. Don't edit these files by hand.

## Updates

RepoHub checks for updates in the background and always asks before installing one. You can check yourself with **Settings → App updates → Check for Updates…**. It will not install an update while a backup is running.

## Restore a backup

Backups are ordinary `.tar.gz` archives, so you don't need RepoHub to restore one. **Always extract into a new, empty folder, never over a folder you are still using.**

1. In Finder, open your backup folder and then the subfolder for the repo you want. If the archive shows a cloud with a down arrow (it isn't downloaded to this Mac yet), use Finder’s download action and wait until the archive can be read locally.
2. Check that the file is intact. RepoHub’s `index.json` records SHA-256 checksums for current archives and retained outside items. It is not a checksum history of every archive. Print the recorded values, then compute the checksum of the file you downloaded:

   ```bash
   # On the Mac that made the backup:
   INDEX=~/Library/Application\ Support/RepoHub/backups.json
   # On any other Mac: use the index.json file in your iCloud backup folder instead, for example
   # INDEX="$HOME/Library/Mobile Documents/com~apple~CloudDocs/<your backup folder>/index.json"

   python3 -c "import json,sys; d=json.load(open(sys.argv[1])); [print(e['sha256'], e['archive']) for v in d.values() for e in [v, *(v.get('linked') or {}).values(), *(v.get('checkouts') or {}).values(), *(v.get('removed') or {}).values()]]" "$INDEX"
   shasum -a 256 "<path to the archive>"
   ```

   The list includes the separate archives of any linked folders or checkouts you chose to include, and items kept for 30 days after removal. Find the recorded line whose path ends with the repo's folder name and the archive's exact file name (for example `.../MyProject/2026-11-23T10-00-00.123456Z.tar.gz`). For a linked folder or checkout the path continues through its `linked/<name>/` or `checkouts/<name>/` subfolder. If two repos share a folder name, include the parent folder that tells them apart. File names are only dates, so another repo's archive can look similar; match both parts. **The two long hex values must be identical. If they differ, or you can't find a matching line, stop: do not extract. Download the archive again, and if it still differs, report it.**
3. Extract into a new folder:

   ```bash
   RESTORE=~/Restored-$(date +%Y%m%d-%H%M%S)
   mkdir "$RESTORE" && tar -xzf "<path to the archive>" -C "$RESTORE" && echo "Restored into $RESTORE"
   ```

   The folder name includes the time to the second. If that name already exists, making it fails and nothing is extracted, so pasting twice can't overwrite an earlier restore. The archive contains your folder under its own name, including `.git`, uncommitted and ignored files.
4. **Included linked folders and checkouts are separate archives.** If you chose to include one, repeat steps 1 to 3 for its own archive (its path sits in a subfolder beside the repo's archive), extracting it into its own new folder. Don't copy restored contents over live folders; if you need them in place, move the original aside first. A linked **Git checkout** (worktree) restores as files plus a `.git` pointer file that still names the **original** repository, which may be the live one on this Mac, and the original repository's record of it is not restored with the checkout. Treat a restored checkout as plain files and don't run Git commands inside it. If you need a working checkout, make a new one from your restored repository with `git worktree add` and copy the files across **without** the `.git` file (for example `rsync -a --exclude .git "$RESTORED_CHECKOUT/" "$NEW_CHECKOUT/"`), so the new checkout can't be re-pointed at live Git data.
5. Look through the restored folder before you rely on it. Don't run its scripts or tests until you trust it. If the folder had links to places outside it, they are restored as links with the same target text. An absolute target still points at the original location, so editing through it would change those live files, and a relative one may lead somewhere unexpected from the restored folder. Check with `ls -l` before you edit anything that looks like a link.

**Only the newest backup is kept.** RepoHub is a safety copy, not a version history. After you delete or break a file and a backup runs, the new archive reflects that. The previous archive is kept only until the new one is verified and confirmed uploaded, and is then deleted, so older versions of uncommitted or ignored files can't be recovered afterwards. Committed Git history is included when the selected folder contains the corresponding Git object store. The committed history of a linked Git checkout lives in its parent repository's archive; including the checkout also saves its working files, including uncommitted changes, as a separate archive. If you want to keep a known-good copy, copy the archive somewhere else before the next backup replaces it, and note its SHA-256 (`shasum -a 256`) beside the copy, because a later replacement archive supersedes the current checksum in the index.

**To check that another Mac can retrieve and extract the recorded archive,** do steps 1 to 3 on a different Mac signed in to the same iCloud account, so the file really came from iCloud and not from the Mac that made it. If the checksum matches RepoHub's record, the bytes are identical.

## Uninstall

1. Click **Quit** in the panel.
2. Drag **Repo Hub.app** from Applications to the Trash.
3. Optional: remove it from System Settings → General → Login Items & Extensions, and delete `~/Library/Application Support/RepoHub` if you don't want its settings.

Your backups in iCloud Drive are not touched. Delete them yourself when you no longer need them.
