---
type: is
id: is-01m0nw7vg2kzh80g7vvvk1h28q
title: Make the navigation tally incremental and retire the staleness apparatus (H34/S1)
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:35.874Z
updated_at: 2026-11-14T18:41:50.340Z
---
Review suggestion S1. exp-003 and exp-007 both work AROUND the cost of an O(index) tally pass rather than removing it. The tallies are sums over per-entry attributes and every mutation already funnels through _replace_index_entry/_pop_index_entry under one lock. Add/subtract there and the pass is O(1) amortized: no memo, no staleness bound, no derived-cost heuristic, no residual GIL contention with the walker. Recency windows are the only clock-dependent part and are already answered from sorted mtimes. This is the fix the bound is standing in for.

## Notes

2026-11-14 audit, from mb-65mg (closed as a duplicate of this bead): the tally memo is keyed on the index revision, and recency windows are a binary search over per-revision sorted array('q') mtimes, tracked and ignored (python_inventory.py, _compute_navigation_tallies), so the clock is out of the key. #413 made one pass about 4x cheaper (1,694-1,739 ms to 373-374 ms at 300,000 entries) and lets readers that arrive during a pass share the next one (_read_navigation_sync). What remains is maintaining the extension, canonical-extension, family and preset counters per write in _replace_index_entry and _pop_index_entry, and keeping the sorted mtime arrays sorted under insertion and removal, where an arbitrary removal from a sorted array is O(n). Measure with devtools/bench_serving.py's scan-with-a-client-attached tree row.
