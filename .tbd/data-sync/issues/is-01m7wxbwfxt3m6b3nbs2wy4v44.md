---
type: is
id: is-01m7wxbwfxt3m6b3nbs2wy4v44
title: "Source kind icon: one icon per checkout kind (cloud mirror, local Git or GitHub checkout, local plain folder) beside the root name at the top of the nav, with a tooltip naming the kind, matching the macOS title-bar menu, Open Recent and Dock menu, recorded in the design system"
kind: feature
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T16:41:50.331Z
updated_at: 2026-11-20T16:44:00.099Z
started_at: 2026-11-20T16:44:00.015Z
---
Owner request (2026-11-20, asked before and not tracked): the nav column's root name gets a leading icon for what is open, and it matches the macOS title bar folder menu's icon for the same thing. Tooltip says the kind (for example 'Cloud mirror of owner/repo', 'Local Git checkout', 'Local folder'). Three modes: cloud mirror; local folder that is a Git repository (GitHub or not, with the remote noted where it is GitHub); local plain folder. The same three icons are used everywhere a source appears (nav root, title-bar path menu, Open Recent, Dock menu, folder chooser rows), and the design system's icon catalog gets a Source kind section with a check. Related: mb-o7s8, mb-z822, mb-48rf.

## Notes

Owner, 2026-11-20: a checkout-kind icon (the source's root) must differ from the generic folder icon used for ordinary subfolders in the tree, Files view and elsewhere. The design system defines both families: source kinds (cloud mirror, local Git or GitHub checkout, local plain folder) and the ordinary folder (open and closed), and says where each is used. The same rule applies in the macOS app's menus.
