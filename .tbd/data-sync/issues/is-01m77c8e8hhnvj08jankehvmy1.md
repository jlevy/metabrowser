---
type: is
id: is-01m77c8e8hhnvj08jankehvmy1
title: "macOS app: the live EOF test must prove a ready server releases its port (review C4, #363)"
kind: task
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels:
  - macos
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T07:58:48.592Z
updated_at: 2026-11-12T08:20:39.468Z
started_at: 2026-11-12T07:58:54.429Z
closed_at: 2026-11-12T08:20:39.466Z
close_reason: "Fixed in 3ede055e on claude/v1-final-review-lifetimes: bounded announcement wait, readiness probe and held-port check before closing the lifeline, then exit, no answer, and a free port. Old ordering measured: port unbound at announcement in 10 of 10 runs."
resolution: null
duplicate_of: null
---
Review C4 on #363 (mb-niod): LiveMetabTests.aServerWhoseAppIsGoneStopsByItself closes stdin after the announcement, which precedes binding, so the final failed probe does not prove a listening server released its port. Fix: bound the announcement wait, require a successful readiness probe, then close the lifeline and verify exit and loss of service.
