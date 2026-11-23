# Menu-bar information view

The circled information button to the left of Settings opens **About your backups**.
The existing status legend and Things to know content live in that dialog rather
than below the repository details. Close returns to the repo view; Escape uses
the native HTML dialog behavior. Show me closes the dialog before highlighting
the selected repo's folder button. Existing Finder and GitHub bridge actions stay
unchanged. The dialog scrolls within the menu window on smaller displays.

## Navigation and tutorial support

The information button opens both help sections. Navigation
   preserves the status labels and backup logic.
The status model determines which labels appear. Changes to the
   model require corresponding checks of the application logic.
The status graphic should explain each label and the
   evidence needed to display it.
The proposed information-view tutorial would support
   first-launch presentation and repeat access. This behavior is not implemented yet.

Browser preview coverage excludes
release promotion, app installation and
native interaction checks.

## Navigation test coverage

- The Python regression suite uses synthetic fixtures.
- Existing menu-status, report-entry, workspace-setup, diagnostic-delivery and
  readiness JavaScript tests cover the web controllers. Additional checks cover menu syntax and diff formatting.
- The read-only browser preview uses the menu HTML, CSS and JavaScript with live
  helper status. Check button placement, both help sections, opening by
  keyboard, Escape dismissal/focus return, and Show me closing the information
  view, highlighting the selected folder and clearing that highlight afterward.
- Installed native-menu behavior and the full release gate require separate
  validation.
  The preview blocks writes and native actions.


## Status explanations

The information view now explains each current compact label within six visual
categories. It distinguishes strict green success from the informational Finder
exception, hash-confirmed edits from pending work, observed upload from cloud
acknowledgement, and schedule waiting from unavailable checks. All presentation
labels are covered by the shared guide regression. The existing Things to know
content remains; a first-launch/repeatable tutorial is still future work.
