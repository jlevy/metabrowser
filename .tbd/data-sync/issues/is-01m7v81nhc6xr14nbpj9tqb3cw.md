---
type: is
id: is-01m7v81nhc6xr14nbpj9tqb3cw
title: "Title folder menu: the cloud or folder icon sits on the name's line, not centered across the two-line row"
kind: bug
status: closed
priority: 2
version: 6
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T01:10:01.003Z
updated_at: 2026-11-20T17:00:14.416Z
started_at: 2026-11-20T01:12:38.418Z
closed_at: 2026-11-20T02:39:54.466Z
close_reason: "Merged in PR 628. Check mark stays centered on two-line rows: a custom onStateImage loses AXMenuItemMarkChar (accessibility checked state), so the accessible native check was kept."
resolution: null
duplicate_of: null
---
Owner, 2026-11-19, verbatim: "in the dropdown menu in the title, the cloud and folder icons should be to the left of the name of the foler or repo, not centered vertically as they are now. i.e. they should be on the same line as the main name and the smaller text below should be subsequent lines". Likely apps/macos/Sources/Metabrowser/FolderChooserMenu.swift (each.image = row.mark.image on a two-line item) and the same pattern in RecentTargetsMenu.swift and TitleAccessory.swift; RootMark.swift maps folder/cloud.

## Notes

PR #628 (claude/title-menu-icon-first-line). A subtitled menu item gets the mark at the top of an image 2 x 7 pt taller (RootMark.TitleLineLayout, rise measured on macOS 26.5), which AppKit centers onto the title's line; items stay plain NSMenuItems, so highlight, check mark, Option alternates, keys and accessibility are AppKit's. Switch Folder panel rows center the mark on the title label to match. Hand check steps 3 and 11 (qa-macos-app-hand-checks.md, Switching Folders) updated, not yet run on an installed app.

Review A folded in 1893895e7: NSMenuItem.setMark sets subtitle and mark together (replaces RootMark.image(for:)) and keeps the subtitle to one line, middle-truncated when AppKit would wrap it (FolderChooser.oneLine, measured with NSMenu.size, cached), full text in the tooltip. A3 (check mark on the name's line via a custom onStateImage) not done: any custom onStateImage drops AXMenuItemMarkChar on macOS 26.5, so the check stays AppKit's, centered on the row; returned to the coordinator.
