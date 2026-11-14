---
type: is
id: is-01m0jt3f1hdn6aqt75q7ct5bpn
title: "R5: make the recency filter cacheable via sorted mtimes and binary search"
kind: feature
status: open
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m0gfpa3nt74hvrnqbyqhn0ya
created_at: 2026-08-21T18:42:31.600Z
updated_at: 2026-11-14T18:43:35.073Z
---
PR #60 review R5 (an opportunity, not a defect), restated against the provider code on main.

A filtered navigation tree (FilteredTreeQuery, answered by _filtered_tree_projection in src/metabrowser/inventory_engine/providers/python_inventory.py) is a full pass over the index on every request. Only its continuation pages are memoized (_FilteredTreePageMemo), and that memo matches on the whole filter. A recency filter's cutoff carries as_of_ns, so no two requests with a recency filter can share an answer. One filter change fans out into the tree request plus a subtree request per lazy stub the prefetch sweep warms.

The navigation tallies solved the same clock dependency. _NavigationTallyBase keeps sorted tracked and ignored mtimes per revision, and _with_recency answers each window by binary search, so the memoized half carries no clock term (arch-state-and-delivery.md, What Is Not Solved). Apply the same shape here: memoize the clock-independent filtered result per revision and filter, and answer the recency cutoff from sorted mtimes. Measure the pass on a large tree first.

## Notes

Deferred from the PR #60 review as agreed: an opportunity, not a defect. The pattern to reuse is _with_recency in inventory.py on main — a per-revision sorted array of mtimes answered by binary search, so the memo key carries no clock term. Do it before the prefetch sweep meets a large tree: today a recency filter runs the full O(index) pass on every request in the fan-out.
