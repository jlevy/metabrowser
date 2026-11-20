---
type: is
id: is-01m7s898skvvqr3pjh0h263x1q
title: Merge drawerFilterCount into filterState.activeCount now that both count the same four filters
kind: task
status: open
priority: 4
version: 3
labels: []
dependencies: []
parent_id: is-01m7wys3bp2ndx4v4m26exf0hz
created_at: 2026-11-19T06:35:41.234Z
updated_at: 2026-11-20T17:09:21.811Z
---
From PR #601 review A1: after Show ignored moved into the Files drawer (mb-ey0d), tree-filter-model.js drawerFilterCount(state) equals filterState.activeCount() for every valid state. One of them can go.

## Notes

2026-11-19: #605 (Drop the filter chevron's count badge so Clear fits beside it) merged into main 13cb9bc11. Recheck what still reads drawerFilterCount before merging it into activeCount; it may now be removable outright.
