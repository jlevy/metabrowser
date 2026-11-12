---
type: is
id: is-01m748xta3y5hxhf6kx1n8psja
title: Open a file from open -a and select it inside its folder
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:51.458Z
updated_at: 2026-11-12T01:25:37.584Z
started_at: 2026-11-12T00:37:58.780Z
closed_at: 2026-11-12T01:25:37.582Z
close_reason: "open -a and File > Open accept a file: OpenTarget maps it to the most specific open folder containing it, else its own folder, and the window navigates to the file's view route (PageAddress.view, checked live against metab --path). Commits 8abce832, 41618d0a, 95efdc91 on claude/v1-everyday; end-to-end run of a check build confirmed the route and one server per folder."
resolution: null
duplicate_of: null
---
Phase 2. The app refuses files today; accept one, open its folder, and select the file.
