---
type: is
id: is-01m7wxbwfxt3m6b3nbs2wy4v44
title: "Source kind icon: one icon per checkout kind (cloud mirror, local Git or GitHub checkout, local plain folder) beside the root name at the top of the nav, with a tooltip naming the kind, matching the macOS title-bar menu, Open Recent and Dock menu, recorded in the design system"
kind: feature
status: in_progress
priority: 1
version: 5
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7wyrvxk2xx44pqtqmy5cq5g
hold: null
hold_until: null
created_at: 2026-11-20T16:41:50.331Z
updated_at: 2026-11-20T17:58:02.353Z
started_at: 2026-11-20T16:44:00.015Z
---
Owner request (2026-11-20, asked before and not tracked): the nav column's root name gets a leading icon for what is open, and it matches the macOS title bar folder menu's icon for the same thing. Tooltip says the kind (for example 'Cloud mirror of owner/repo', 'Local Git checkout', 'Local folder'). Three modes: cloud mirror; local folder that is a Git repository (GitHub or not, with the remote noted where it is GitHub); local plain folder. The same three icons are used everywhere a source appears (nav root, title-bar path menu, Open Recent, Dock menu, folder chooser rows), and the design system's icon catalog gets a Source kind section with a check. Related: mb-o7s8, mb-z822, mb-48rf.

## Notes

Owner, 2026-11-20: a checkout-kind icon (the source's root) must differ from the generic folder icon used for ordinary subfolders in the tree, Files view and elsewhere. The design system defines both families: source kinds (cloud mirror, local Git or GitHub checkout, local plain folder) and the ordinary folder (open and closed), and says where each is used. The same rule applies in the macOS app's menus.

PR #667 (branch claude/source-kind-icons). Glyphs (Lucide 1.17.0): mirror = cloud, Git checkout = folder-git-2, plain folder = folder-dot; ordinary folder = folder (open variant folder-open defined in the catalog, not drawn: tree rows lead with a chevron). folder-root was tried and dropped: it reads as a keyhole at 14 px.
The page's glyphs are in static/source-kind-glyphs.json, written by the server into the first paint (source_kind_marks.py), not in static/icons.js: the registry pushed startup_script_transfer_kb 707 bytes over its 220 KB gate. /api/identity kind is folder|git|mirror (git = the root holds a .git entry, as the Commits tab is decided), kind_label is Local folder / Local Git checkout / Cloud mirror, kind_tip is the tooltip sentence. recent-targets entries gain optional git (no format bump). The macOS app draws the same Lucide path data as a template image (RootMark), not an SF Symbol; RootMarkTests and tests/test_icon_catalog.py hold the pairing. App contract entry in changelog.d/mb-4s2y.md; MetabRequirement.minimumRelease stays 0.13.0.
Open for the owner: the main pane's header for the root folder still draws the ordinary folder icon beside the root name; mb-wup3's indicator part is covered by this PR, its other parts (stating the mode in every view) are not.
Screenshots (gitignored): attic/source-kind-shots/ in the review-527-b worktree.
