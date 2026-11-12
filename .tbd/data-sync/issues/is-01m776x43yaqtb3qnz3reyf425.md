---
type: is
id: is-01m776x43yaqtb3qnz3reyf425
title: "Review A2 on #363: a pair missing both measurements can disappear from the gate's verdict"
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
created_at: 2026-11-12T06:25:14.877Z
updated_at: 2026-11-12T06:58:52.635Z
started_at: 2026-11-12T06:25:21.265Z
closed_at: 2026-11-12T06:58:52.634Z
close_reason: "Fixed in b844bf0f and fc914e0c (#363): webkit-gate/summary.mjs judges every requested pair in both engines; summary.test.mjs covers one- and two-sided failures and missing pairs."
resolution: null
duplicate_of: null
---
summarize() in webkit-gate/run.mjs judged completeness against the pairs that supplied a metric. Validate each metric against the requested pairs and both engines, so a missing or failed measurement is incomplete, never pass; add Node aggregation tests.
