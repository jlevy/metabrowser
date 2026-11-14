---
type: is
id: is-01m0pe6qpyhzne1b8n83mghdyz
title: "H53: count region repaints as a standing metric, then reduce them"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T04:31:33.597Z
updated_at: 2026-11-14T18:46:46.026Z
closed_at: 2026-11-14T18:46:46.025Z
close_reason: "Done: tree_region_repaints is a required standing metric (run.py METRICS, performance-budgets.toml maximum 1, accept-rule item 4) and the tree region paints once per load since exp-014 (mb-izxl); viewport-wide coverage is H56's visual_states (mb-unt6)."
resolution: null
duplicate_of: null
---
exp-009 added tree_region_repaints and found 3 paints of the tree region per load: inlined rows, fetched rows, refresh. Each is a visible replacement of the whole panel (filesPanel.innerHTML = ...). H11 is the fix (patch rather than replace); this is the metric that makes it checkable, and it should extend beyond the tree region to the preview pane and the filter bar. Metric: repaints per region per load, target 1.

## Notes

Regime note from the exp-009 re-measure: the count is 3 on a cold load and 4 against a settled index, which adds the summary refresh pass. A future run that reads 4 has not regressed -- compare within a regime. The metric is now in run.py's METRICS list, so 'run.py compare' prints it per condition.
