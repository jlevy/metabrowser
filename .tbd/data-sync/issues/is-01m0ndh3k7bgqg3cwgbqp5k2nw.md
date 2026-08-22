---
type: is
id: is-01m0ndh3k7bgqg3cwgbqp5k2nw
title: Tree rows respond without waiting for the tally pass (H27)
kind: task
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T19:00:30.433Z
updated_at: 2026-08-22T22:09:53.586Z
closed_at: 2026-08-22T22:09:53.585Z
close_reason: "Landed: a row request serves navigation tallies only from a fresh memo and never computes them; depth=0 is the channel that pays, fetched behind the render by the existing scheduleRootSummaryRefresh. probe-server on /api/tree?depth=2 during a scan: official corpus 311ms -> 2ms, real tree A 777ms -> 6ms, real tree B 67ms -> 1ms, all non-overlapping. Side effect: attached walk on tree A 70.2s -> 50.0s, because the request cost was stealing CPU from the walker. exp-007."
---
Even with exp-003's staleness bound, the FIRST root request during a scan pays the cold O(index) tally pass — load_tree_ms stayed near a second while repeat-request cost fell to 394ms — because rows and tallies share one JSON body. Decouple: rows respond immediately, tallies arrive separately (second cheap request or the stream). updateFilterTallies already guards every field, so a tally-less payload is tolerated today. Metric: load_tree_ms during a scan -> tens of ms. Run after mb-6t3n (realistic corpus).
