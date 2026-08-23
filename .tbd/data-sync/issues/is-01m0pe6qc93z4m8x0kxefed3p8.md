---
type: is
id: is-01m0pe6qc93z4m8x0kxefed3p8
title: "H52: the shell ships placeholders, not a skeleton"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T04:31:33.256Z
updated_at: 2026-08-23T07:12:32.707Z
---
Measured off the wire: #nav-filter-bar is empty, #tab-files is 'Loading files...', #preview-pane is 'Select a file to preview.', #index-progress is 'Scanning...'. So the first paint is chrome plus three text placeholders, each replaced wholesale. exp-009 stopped the page MOVING; it did not make the structure appear complete. Server-rendering a real row-shaped skeleton -- resting-state filter chips, placeholder tree rows -- would. The obstacle is duplication: the chip markup lives only in filter_controls.js, so a server-side counterpart needs a shared source or it drifts, which is what AGENTS.md warns about. Metric: skeleton_complete at first paint, and region repaint count.

## Notes

Baseline for this bead, measured by the reworked probe on the fixed 246,282-file corpus at 1280x900: frame_missing_px = 615. Per region, settled vs what the shell ships: #nav-filter-bar 37/37, #preview-pane 900/900, #tab-files 636/21. So the whole gap is the files panel -- 615px of rows where the server ships one 21px line of 'Loading files...'.

frame_missing_px is now in probe.js and in run.py's METRICS, so 'run.py compare' prints it per condition and this bead can be scored rather than argued. Target is 0, or as near as a server-rendered skeleton can get.

Note the metric it replaced: skeleton_complete asked whether each region was present, sized and non-empty at probe time, which is after settle. It returned true on all 10 runs ever recorded, including every one where this 615px gap was present. It could not come out false.
