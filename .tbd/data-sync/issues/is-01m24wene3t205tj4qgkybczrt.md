---
type: is
id: is-01m24wene3t205tj4qgkybczrt
title: Eliminate v0.9.1-to-current browser repaint and frame regression
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m24nhxxpkrb7cvgyvtxb5d0r
created_at: 2026-09-10T05:25:37.346Z
updated_at: 2026-09-10T17:49:02.801Z
closed_at: 2026-09-10T17:49:02.800Z
close_reason: "Completed by exp-031: the candidate restored the one-paint root reconciliation contract and improved the missing-frame result relative to v0.9.1 while all headed-browser hard gates passed across five runs per build."
resolution: null
duplicate_of: null
---
The exact v0.9.1-to-f097c667 release comparison is backend-equivalent and passes hard browser budgets, but all three candidate profiles report tree_region_repaints=2 versus 1 and frame_missing_px=509 versus 269. The release performance accept rule blocks a repeatable wrong-way repaint or missing-frame result. Diagnose and fix, or document a justified acceptance with matching evidence.
