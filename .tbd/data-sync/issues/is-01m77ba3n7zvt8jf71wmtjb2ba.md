---
type: is
id: is-01m77ba3n7zvt8jf71wmtjb2ba
title: "Review B1 on #363: a summary without a pair count can still read complete"
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
created_at: 2026-11-12T07:42:14.692Z
updated_at: 2026-11-12T07:42:20.991Z
started_at: 2026-11-12T07:42:20.989Z
---
summarize() in webkit-gate/summary.mjs defaulted a missing meta.pairs to 0 and took the observed pairs as the expected ones, so a missing middle or trailing pair disappeared and the result could read pass and complete. Require a valid positive integer count before any completeness or pass verdict; otherwise report completeness as unknown.
