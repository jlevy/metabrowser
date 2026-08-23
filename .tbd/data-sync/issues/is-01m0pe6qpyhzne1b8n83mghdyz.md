---
type: is
id: is-01m0pe6qpyhzne1b8n83mghdyz
title: "H53: count region repaints as a standing metric, then reduce them"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T04:31:33.597Z
updated_at: 2026-08-23T04:31:33.597Z
---
exp-009 added tree_region_repaints and found 3 paints of the tree region per load: inlined rows, fetched rows, refresh. Each is a visible replacement of the whole panel (filesPanel.innerHTML = ...). H11 is the fix (patch rather than replace); this is the metric that makes it checkable, and it should extend beyond the tree region to the preview pane and the filter bar. Metric: repaints per region per load, target 1.
