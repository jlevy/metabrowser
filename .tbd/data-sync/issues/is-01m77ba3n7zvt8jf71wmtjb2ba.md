---
type: is
id: is-01m77ba3n7zvt8jf71wmtjb2ba
title: "Review B1 on #363: a summary without a pair count can still read complete"
kind: bug
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
created_at: 2026-11-12T07:42:14.692Z
updated_at: 2026-11-12T08:02:42.006Z
started_at: 2026-11-12T07:42:20.989Z
closed_at: 2026-11-12T08:02:42.005Z
close_reason: "Fixed in 20bd7013 (#363): summarize() requires a whole pair count of at least one; without one, completeness is null and gated verdicts read pair count unknown."
resolution: null
duplicate_of: null
---
summarize() in webkit-gate/summary.mjs defaulted a missing meta.pairs to 0 and took the observed pairs as the expected ones, so a missing middle or trailing pair disappeared and the result could read pass and complete. Require a valid positive integer count before any completeness or pass verdict; otherwise report completeness as unknown.
