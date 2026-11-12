---
type: is
id: is-01m77bva2e35xdk16hwm6n6t82
title: A stop never signals a group reaped before its spawn returns (#366 review B2)
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
created_at: 2026-11-12T07:51:38.316Z
updated_at: 2026-11-12T08:36:40.700Z
started_at: 2026-11-12T07:51:50.075Z
closed_at: 2026-11-12T08:36:40.699Z
close_reason: Fixed in 7197f37f, subsumed by 0e02c5ac on claude/cli-exit-on-eof (#366 review B2).
resolution: null
duplicate_of: null
---
Review B on #366, B2: the late-registration kill in git/process.py called os.killpg(proc.pid) without checking that the child was unreaped.
