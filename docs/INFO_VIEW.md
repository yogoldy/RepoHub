# Menu-bar information view

The circled information button to the left of Settings opens **About your backups**.
The existing status legend and Things to know content live in that dialog rather
than below the repository details. Close returns to the repo view; Escape uses
the native HTML dialog behavior. Show me closes the dialog before highlighting
the selected repo's folder button. Existing Finder and GitHub bridge actions stay
unchanged. The dialog scrolls within the menu window on smaller displays.

## Agreed sequence — October 16, 2026

1. Add the information button and move both existing help sections there. This
   is the current implementation; existing status labels and backup logic stay intact.
2. Discuss a simpler status model with Leo. After agreement, change the relevant
   application logic, validate it and commit separately.
3. After that validation passes, update the explanatory status graphic in a
   separate commit. Explain the labels and their evidence requirements.
4. Brainstorm the tutorial, then implement it within the information view with
   first-launch presentation and repeat access. This behavior is not implemented yet.

Work proceeds one step at a time without delegated agents. This change does not
promote the pending reliability release, install an app, or resume its unfinished
two-Mac acceptance matrix.

## Validation of this navigation change

- All 204 synthetic Python regressions passed.
- Existing menu-status, report-entry, workspace-setup, diagnostic-delivery and
  readiness JavaScript checks passed; menu JavaScript syntax and diff checks passed.
- Read-only browser preview used the changed menu HTML/CSS/JavaScript with live
  helper status. Verified button placement, both moved sections, opening by
  keyboard, Escape dismissal/focus return, and Show me closing the information
  view, highlighting the selected folder and clearing that highlight afterward.
- Installed native-menu behavior and release Golden Gate are not acceptance
  evidence for this change yet. Neither Mac was deployed and no protected PR
  promotion occurred. The preview blocks writes and native actions.
