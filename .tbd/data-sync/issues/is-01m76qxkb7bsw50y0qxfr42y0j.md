---
type: is
id: is-01m76qxkb7bsw50y0qxfr42y0j
title: "App: a file dropped on a window does nothing"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T02:03:21.830Z
updated_at: 2026-11-12T05:45:52.091Z
started_at: 2026-11-12T05:45:52.089Z
---
From the WebKit gate's checks: dropping a folder opens it, but dropping a file does nothing: the page sees dragenter and dragover, WebKit asks to navigate to the file:// URL, and the navigation policy cancels it. Route a dropped file through the open-a-file path (OpenTarget, mb-tssz) instead.
