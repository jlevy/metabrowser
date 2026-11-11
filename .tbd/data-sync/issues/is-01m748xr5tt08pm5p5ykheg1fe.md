---
type: is
id: is-01m748xr5tt08pm5p5ykheg1fe
title: "Native window title: bold short name, dim bullet and Metabrowser"
kind: feature
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:49.273Z
updated_at: 2026-11-11T03:08:05.315Z
started_at: 2026-11-11T03:08:05.313Z
---
Phase 1, spike branch. Each window shows the short name prominent and bold, then a small bullet and Metabrowser in a secondary style; the window's plain title (Window menu, Mission Control) is the same text; the tab title is the short name; the subtitle or tooltip carries the full name and kind; representedURL gives the proxy icon for local folders. Data comes from GET /api/identity; the formatting is a ShellCore function with unit tests.
