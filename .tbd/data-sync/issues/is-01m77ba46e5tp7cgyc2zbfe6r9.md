---
type: is
id: is-01m77ba46e5tp7cgyc2zbfe6r9
title: "Review B2 on #363: bring apps/macos/webkit-gate under Biome and a strict check-JS project"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T07:42:15.245Z
updated_at: 2026-11-12T08:02:42.378Z
started_at: 2026-11-12T07:42:21.377Z
closed_at: 2026-11-12T08:02:42.376Z
close_reason: "Fixed in 767ae9f3 (#363): Biome, devtools/lint.py, make format, and a strict apps/macos/webkit-gate/tsconfig.json with @types/node cover the gate; probe.js joins tsconfig.json; a violation now fails make lint-check."
resolution: null
duplicate_of: null
---
biome.json, devtools/lint.py, and the TypeScript projects did not cover apps/macos/webkit-gate, so make lint-check gave no lint or type evidence for the gate's JavaScript. Include it in Biome's scope and the Make-driven format and lint commands, add a strict check-JS project with the types it needs, run it from make lint-check, and show a violation fails.
