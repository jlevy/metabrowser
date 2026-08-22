---
type: is
id: is-01m0nw7vg2kzh80g7vvvk1h28q
title: Make the navigation tally incremental and retire the staleness apparatus (H34/S1)
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:35.874Z
updated_at: 2026-08-22T23:17:35.874Z
---
Review suggestion S1. exp-003 and exp-007 both work AROUND the cost of an O(index) tally pass rather than removing it. The tallies are sums over per-entry attributes and every mutation already funnels through _replace_index_entry/_pop_index_entry under one lock. Add/subtract there and the pass is O(1) amortized: no memo, no staleness bound, no derived-cost heuristic, no residual GIL contention with the walker. Recency windows are the only clock-dependent part and are already answered from sorted mtimes. This is the fix the bound is standing in for.
