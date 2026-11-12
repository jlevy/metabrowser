---
type: is
id: is-01m776x43yaqtb3qnz3reyf425
title: "Review A2 on #363: a pair missing both measurements can disappear from the gate's verdict"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T06:25:14.877Z
updated_at: 2026-11-12T06:25:21.266Z
started_at: 2026-11-12T06:25:21.265Z
---
summarize() in webkit-gate/run.mjs judged completeness against the pairs that supplied a metric. Validate each metric against the requested pairs and both engines, so a missing or failed measurement is incomplete, never pass; add Node aggregation tests.
