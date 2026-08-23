---
type: is
id: is-01m0ppz3m2z464j1m2zqvpm4gk
title: "H11: patch the tree panel instead of replacing it, so a load is one paint not three"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T07:04:40.832Z
updated_at: 2026-08-23T07:20:03.682Z
---
exp-010 measured this as a regression the campaign introduced, not a standing cost: the tree region was painted once before the performance work and is painted three times after (inlined rows, fetched rows, refresh). Each pass is filesPanel.innerHTML = ..., which destroys and rebuilds every row.

This is the largest remaining source of the visible flicker on load and reload. Geometry is now stable (exp-009) but the DOM under it is still torn down and rebuilt twice after first paint.

Metric: tree_region_repaints, target 1, measured by probe.js and printed by 'run.py compare'. Secondary: the long-task measure around renderTreeNodes:root.

Same code that row windowing (H7) has to change anyway. See exp-010 and explorations/performance-loop/report.md.
