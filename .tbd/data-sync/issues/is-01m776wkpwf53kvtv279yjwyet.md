---
type: is
id: is-01m776wkpwf53kvtv279yjwyet
title: Stopping kills Git groups whose spawn is in flight; refuses new ones (#366 review A1, A6)
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T06:24:58.075Z
updated_at: 2026-11-12T07:01:18.335Z
started_at: 2026-11-12T06:25:04.639Z
closed_at: 2026-11-12T07:01:18.335Z
close_reason: Fixed in b72a1d63 on claude/cli-exit-on-eof (#366 review A1 and A6; shared stop mechanism for Ctrl-C, hangup, and EOF).
resolution: null
duplicate_of: null
---
Review A on #366, A1: kill_live_process_groups snapshots the registry while spawns may be between fork and registration, on both the EOF and the Ctrl-C paths. A6: docs overstate which Git is killed.
