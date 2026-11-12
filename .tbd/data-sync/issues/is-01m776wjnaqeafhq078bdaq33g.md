---
type: is
id: is-01m776wjnaqeafhq078bdaq33g
title: "exit-on-eof: a nonblocking stdin is waited on, not read as EOF (#366 review A4)"
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
created_at: 2026-11-12T06:24:57.001Z
updated_at: 2026-11-12T06:25:03.937Z
started_at: 2026-11-12T06:25:03.936Z
---
Review A on #366, A4: BlockingIOError from an inherited O_NONBLOCK stdin is treated as EOF while the writer is alive.
