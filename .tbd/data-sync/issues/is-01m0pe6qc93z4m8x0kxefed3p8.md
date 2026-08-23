---
type: is
id: is-01m0pe6qc93z4m8x0kxefed3p8
title: "H52: the shell ships placeholders, not a skeleton"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T04:31:33.256Z
updated_at: 2026-08-23T04:31:33.256Z
---
Measured off the wire: #nav-filter-bar is empty, #tab-files is 'Loading files...', #preview-pane is 'Select a file to preview.', #index-progress is 'Scanning...'. So the first paint is chrome plus three text placeholders, each replaced wholesale. exp-009 stopped the page MOVING; it did not make the structure appear complete. Server-rendering a real row-shaped skeleton -- resting-state filter chips, placeholder tree rows -- would. The obstacle is duplication: the chip markup lives only in filter_controls.js, so a server-side counterpart needs a shared source or it drifts, which is what AGENTS.md warns about. Metric: skeleton_complete at first paint, and region repaint count.
