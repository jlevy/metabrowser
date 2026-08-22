---
type: is
id: is-01m0ndh3k7bgqg3cwgbqp5k2nw
title: Tree rows respond without waiting for the tally pass (H27)
kind: task
status: open
priority: 0
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T19:00:30.433Z
updated_at: 2026-08-22T19:00:30.433Z
---
Even with exp-003's staleness bound, the FIRST root request during a scan pays the cold O(index) tally pass — load_tree_ms stayed near a second while repeat-request cost fell to 394ms — because rows and tallies share one JSON body. Decouple: rows respond immediately, tallies arrive separately (second cheap request or the stream). updateFilterTallies already guards every field, so a tally-less payload is tolerated today. Metric: load_tree_ms during a scan -> tens of ms. Run after mb-6t3n (realistic corpus).
