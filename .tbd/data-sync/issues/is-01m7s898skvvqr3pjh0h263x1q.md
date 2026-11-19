---
type: is
id: is-01m7s898skvvqr3pjh0h263x1q
title: Merge drawerFilterCount into filterState.activeCount now that both count the same four filters
kind: task
status: open
priority: 4
version: 2
labels: []
dependencies: []
created_at: 2026-11-19T06:35:41.234Z
updated_at: 2026-11-19T07:50:04.219Z
---
From PR #601 review A1: after Show ignored moved into the Files drawer (mb-ey0d), tree-filter-model.js drawerFilterCount(state) equals filterState.activeCount() for every valid state. One of them can go.

## Notes

2026-11-19: #605 (Drop the filter chevron's count badge so Clear fits beside it) merged into main 13cb9bc11. Recheck what still reads drawerFilterCount before merging it into activeCount; it may now be removable outright.
