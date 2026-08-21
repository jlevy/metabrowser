---
type: is
id: is-01m0jt2jv9ts6y32me52ep67yt
title: "R2: merged root request takes two snapshots and two O(index) passes"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0jt1hr4r6yqhgxkv0bpyayj
created_at: 2026-08-21T18:42:02.728Z
updated_at: 2026-08-21T18:42:02.728Z
---
PR #60 review finding R2 (high). This one auto-merges clean, which is what makes it
dangerous -- nothing flags it.

In the merged api_tree, a root request with a filter active does:

  entries(scope="all-known")                 snapshot 1, for the filter
  rollup_generation()                        unlocked accessor
  to_thread(build_filtered_inventory_tree)   O(index) pass 1
  entries(scope="all-known")                 snapshot 2, for the tallies
  rollup_revision()                          locked accessor, same counter
  to_thread(navigation_tallies)              O(index) pass 2

Both passes are memoized, so the steady state is fine. The snapshots are not, and the cold
cost is doubled on the first request the page makes. #59 measured that pass at 486ms per
100k entries and 2.7s at 400k, which is why it was memoized at all.

Two decisions, and both want a measurement rather than a reading:

- One snapshot taken once and shared by both passes.
- Whether the two passes should be one. They already walk the same entries for overlapping
  reasons: extension and type predicates on every leaf.

Measure with devtools/bench_serving.py; the tree rows report latency against response size,
which is the shape that makes this visible.
