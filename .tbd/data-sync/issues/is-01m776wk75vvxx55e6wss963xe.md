---
type: is
id: is-01m776wk75vvxx55e6wss963xe
title: Stop notices never block on a full stderr (#366 review A2)
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
created_at: 2026-11-12T06:24:57.572Z
updated_at: 2026-11-12T07:01:17.981Z
started_at: 2026-11-12T06:25:04.288Z
closed_at: 2026-11-12T07:01:17.980Z
close_reason: Fixed in e9d4bcc0 on claude/cli-exit-on-eof (#366 review A2; the Ctrl-C notice shares the fix).
resolution: null
duplicate_of: null
---
Review A on #366, A2: the stdin-closed notice (and the Ctrl-C notice) is a blocking os.write, so a full undrained stderr pipe blocks shutdown forever.
