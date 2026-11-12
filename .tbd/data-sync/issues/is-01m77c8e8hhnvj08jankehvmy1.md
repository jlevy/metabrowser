---
type: is
id: is-01m77c8e8hhnvj08jankehvmy1
title: "macOS app: the live EOF test must prove a ready server releases its port (review C4, #363)"
kind: task
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels:
  - macos
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T07:58:48.592Z
updated_at: 2026-11-12T07:58:54.430Z
started_at: 2026-11-12T07:58:54.429Z
---
Review C4 on #363 (mb-niod): LiveMetabTests.aServerWhoseAppIsGoneStopsByItself closes stdin after the announcement, which precedes binding, so the final failed probe does not prove a listening server released its port. Fix: bound the announcement wait, require a successful readiness probe, then close the lifeline and verify exit and loss of service.
