---
type: is
id: is-01m748xr5tt08pm5p5ykheg1fe
title: "Native window title: bold short name, dim bullet and Metabrowser"
kind: feature
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:49.273Z
updated_at: 2026-11-11T14:44:34.390Z
started_at: 2026-11-11T03:08:05.313Z
---
Phase 1, spike branch. Each window shows the short name prominent and bold, then a small bullet and Metabrowser in a secondary style; the window's plain title (Window menu, Mission Control) is the same text; the tab title is the short name; the subtitle or tooltip carries the full name and kind; representedURL gives the proxy icon for local folders. Data comes from GET /api/identity; the formatting is a ShellCore function with unit tests.

## Notes

Implemented on branch claude/macos-window-titles (commit 395979df, unpushed): leading title-bar accessory with bold short name, secondary bullet and Metabrowser, drawn proxy icon and path menu; FolderIdentity/IdentityClient/WindowTitle in ShellCore with tests (99 pass). Falls back to the folder's path on 404 from metab without /api/identity (mb-n9p6). Awaiting visual check (light/dark, key/non-key, narrow widths, drag and double-click, path menu placement) before close.

2026-11-11: Merged into claude/macos-app-spike and pushed to jlevy/metabrowser#341 at 21dae3c3 (not to be merged into main until the user says so).
