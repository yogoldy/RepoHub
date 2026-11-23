# Troubleshooting

Start with the card in the RepoHub panel: its status line and details say what is wrong. If that isn't enough, find your symptom below. For setup help see the [getting started guide](GETTING_STARTED.md).

**Your backups are never deleted to fix a problem.** RepoHub keeps the previous archive until a new one is verified and uploaded, and none of the steps below require you to delete a backup. Normal retention resumes when the helper runs.

## The menu-bar icon isn't there

- **The menu bar is full.** RepoHub uses a macOS status item. Check whether making more room in the menu bar reveals it. Hold ⌘ and drag other icons out of the menu bar, or quit an app you don't need.
- **A menu-bar manager is hiding it.** Apps that hide or reorganize menu-bar icons may hide RepoHub. Check that app's visibility settings and allow RepoHub there.
- **RepoHub isn't running.** Open it from Applications. If it doesn't start, check whether another copy is running (see below).

## The icon shows "!"

RepoHub couldn't reach its backup helper, or the helper and the app don't match. A "!" can also appear when the helper is reachable but a backup or upload needs attention, its checks have become stale, or the app can't display the current status; open the panel to see which.

1. Wait a minute. If the helper stopped unexpectedly, RepoHub restarts it by itself.
2. If "!" stays, click **Quit** in the panel and open RepoHub again.
3. If it still shows "!", see "Another copy of RepoHub is running" next. Then [send a report](#send-a-report).

## "Another copy of RepoHub is running"

Only one copy of RepoHub can run, because the helper uses a fixed local port. This can happen when another copy is already running, for example one in Downloads and one in Applications.

1. Quit RepoHub.
2. Delete the extra copy and keep one in **Applications**.
3. Open RepoHub again.

Your backups and settings are shared and not affected.

## A folder says “Awaiting upload confirmation” or “Uploading” for a long time

Read the card label. “First backup pending” means RepoHub has no current backup record for this folder. “Uploading” means macOS reports a transfer. “Awaiting upload confirmation” means completion has not been confirmed. RepoHub is correct not to show green.

- Check System Settings → your name → iCloud → Drive is on, you're online, and you have free iCloud storage.
- Large folders take a while. RepoHub keeps the older archive until the new one is confirmed uploaded.
- For upload confirmation, read RepoHub’s card. It uses the upload status macOS reports for the backup archive.
- If nothing moves for about 30 minutes, RepoHub raises it as a problem.

## A folder shows a question mark, “Awaiting upload confirmation” or “Upload status unavailable”

macOS may have reported that upload is pending, or RepoHub may lack usable upload evidence for the current archive. RepoHub never turns that into a green check. Check that the destination folder is really inside iCloud Drive, use Finder to inspect the destination, and wait for the next check (about every 5 seconds).

## "Needs attention", "Blocked" or a folder can't be read

Read the reported cause. Check folder permissions for “Access denied,” reconnect missing storage, or address the reported destination, verification or upload error.

1. Open **Settings → Access & permissions** in the panel and choose **Folder privacy settings**.
2. Switch RepoHub on under Files & Folders. RepoHub does not request Full Disk Access. Use Check access to confirm that it can read the selected folder.
3. Run **Check access** again.

If the error names another cause (a folder was moved, a drive is unplugged, the destination is gone), reconnect unavailable storage and choose **Rescan** for the repo. If the source moved or its identity changed, choose **Review monitored folders** and save the corrected selection.

## "Status outdated" or "Waiting for fresh checks"

RepoHub only shows green with recent checks. If it hasn't been able to check lately (the Mac was asleep, or the helper is busy), it says so. Choose **Rescan…** in the overview or **Rescan** followed by the repo name in its details, or wait for the next check.

## A folder keeps saying “Checking again”

Something is writing to the folder while RepoHub tries to verify it (a build, a sync tool, an editor). RepoHub waits for the folder to hold still and tries again. It keeps the previous backup in the meantime. Closing the busy tool, or backing up when it's idle, resolves it.

## A green check, but the details say only `.DS_Store` differs

RepoHub still checks every file. But Finder rewrites its `.DS_Store` view-settings files constantly, so a difference in those alone is deliberately not treated as a change that needs a new backup. The card stays a normal green **Backed up** (once the last archive is confirmed uploaded) and its details say "Only Finder view settings (.DS_Store) differ from the saved backup." At the last content check of the main folder, the only differences found were regular `.DS_Store` files. Included outside folders have separate archives. Nothing is wrong.

## A linked folder's backup says it is unavailable

A folder reached through a link (for example a `node_modules` kept on an external drive) can't be reached right now, usually because the drive is unplugged. RepoHub keeps its last backup and reports it. Reconnect the drive, open the repo’s card and choose **Rescan** followed by the repo name.

## Backups don't resume after a restart

After setup, RepoHub attempts login registration once if needed. Check the reported login state if it does not start at login.

1. Check System Settings → General → **Login Items & Extensions**. Repo Hub should be listed and on. If it asks for approval, approve it.
2. **Settings → Access & permissions** shows a "Login operation" line that says whether it is on, and **Login items settings** opens the right page.

If you turned it off on purpose, RepoHub leaves it off: it makes only one registration attempt and does not switch the item back on.

## macOS says the app "can't be opened"

Only download RepoHub from the project's [Releases page](https://github.com/yogoldy/RepoHub/releases). Stable promotion requires a Developer ID signature and Apple notarization. The Dev channel can also carry personal ad-hoc builds. If macOS blocks the app, record the exact message and use the opening or approval options macOS offers for that release. Don't turn off Gatekeeper. If RepoHub still won't open, you can't use its report button, so [open an issue on GitHub](https://github.com/yogoldy/RepoHub/issues) with your macOS version and the message macOS shows, with any file paths or names removed.

## Notifications don't appear

Notifications are optional. Check System Settings → Notifications → Repo Hub, and your Focus settings. Backups don't depend on notifications.

## Send a report

Use **Settings → Help & diagnostics** in the panel (**Report a glitch** or **Request a feature**).

- You see the exact text and sanitized diagnostics before anything is posted. If you've connected a GitHub account, RepoHub checks that connection while it prepares the preview (a request to GitHub, with no report content). The report itself leaves your Mac when you choose **Send to GitHub** or explicitly **Retry send** after a failure.
- Reports are **public GitHub issues**. Don't include anything confidential.
- RepoHub keeps diagnostics on your Mac (`~/Library/Application Support/RepoHub/diagnostics`) with a seven-day age limit and a 100 MiB size limit applied on writes. Read a summary with `python3 diagnostics_report.py --log-dir "$HOME/Library/Application Support/RepoHub/diagnostics"` from a source checkout.

To report a security problem privately, see [SECURITY.md](../SECURITY.md).
