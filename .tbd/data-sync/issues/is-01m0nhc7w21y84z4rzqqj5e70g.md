---
type: is
id: is-01m0nhc7w21y84z4rzqqj5e70g
title: Inline the first rows when the index is cold (H32)
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T20:07:45.282Z
updated_at: 2026-08-22T20:07:45.282Z
---
exp-004's inline fires only when inventory_has_data(), and on a first open of a real tree the index is empty at page-render time — behind H30's 19-23s gitignore build. Probe recorded inline_rows: null. So the 1,604ms -> 242ms result is conditional on a warm index, i.e. it helps second loads and not first opens, which is the case it was for. Candidate: fall back to one synchronous scandir of the root (~37us measured) when the index cannot answer. Metric: inline_rows non-null and first_row_ms on a FIRST open of a real tree. exp-005.
