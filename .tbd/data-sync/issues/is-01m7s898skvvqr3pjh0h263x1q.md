---
type: is
id: is-01m7s898skvvqr3pjh0h263x1q
title: Merge drawerFilterCount into filterState.activeCount now that both count the same four filters
kind: task
status: open
priority: 4
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T06:35:41.234Z
updated_at: 2026-11-19T06:35:41.234Z
---
From PR #601 review A1: after Show ignored moved into the Files drawer (mb-ey0d), tree-filter-model.js drawerFilterCount(state) equals filterState.activeCount() for every valid state. One of them can go.
