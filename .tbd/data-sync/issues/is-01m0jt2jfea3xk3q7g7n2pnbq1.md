---
type: is
id: is-01m0jt2jfea3xk3q7g7n2pnbq1
title: "R1: keep children_of when merging #60's filtered tree path"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0jt1hr4r6yqhgxkv0bpyayj
created_at: 2026-08-21T18:42:02.349Z
updated_at: 2026-08-21T18:42:02.349Z
---
PR #60 review finding R1 (high).

tree.py:602 on the #60 branch calls _build_inventory_subtree(by_parent=_group_by_parent(entries))
with entries = get_inventory().entries(scope="all-known"). That is the per-request O(index)
grouping #59 removed in db58058. main now passes children_of=inv.children_of and reads the
incremental child index.

Measured on main across that change: folder expansion 63ms -> 7ms at 117k entries, and
/api/tree top00 depth=2 13.3ms -> 3.5ms on the 100k benchmark corpus.

Git conflicts here, so it will be seen. The risk is the resolution: the conflict is large
and intertwined, and taking "ours" restores a full index pass on every expansion.

Do not pick a side. _build_inventory_subtree needs children_of from main for structure and
the new `matches` parameter from #60 for the filter chips. Both fit in one signature: the
filtered path already holds `entries` for filtered_rollups, but here it only needs child
lookup, which children_of does more cheaply. One code path, children_of for structure,
optional matches for aggregates.

Verify with devtools/bench_serving.py: the /api/tree subtree rows must stay at main's
numbers after the merge. Take both sides back to back on one machine.
