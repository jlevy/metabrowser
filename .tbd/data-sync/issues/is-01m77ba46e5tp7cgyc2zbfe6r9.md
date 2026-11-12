---
type: is
id: is-01m77ba46e5tp7cgyc2zbfe6r9
title: "Review B2 on #363: bring apps/macos/webkit-gate under Biome and a strict check-JS project"
kind: task
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
created_at: 2026-11-12T07:42:15.245Z
updated_at: 2026-11-12T07:42:21.378Z
started_at: 2026-11-12T07:42:21.377Z
---
biome.json, devtools/lint.py, and the TypeScript projects did not cover apps/macos/webkit-gate, so make lint-check gave no lint or type evidence for the gate's JavaScript. Include it in Biome's scope and the Make-driven format and lint commands, add a strict check-JS project with the types it needs, run it from make lint-check, and show a violation fails.
