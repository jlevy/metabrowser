---
type: is
id: is-01m0m5vvtarew6gk78b295j1ag
title: Inline the root's depth-1 tree into the shell HTML (H20)
kind: task
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T07:27:19.880Z
updated_at: 2026-08-22T18:36:21.893Z
closed_at: 2026-08-22T18:36:21.892Z
close_reason: "Landed: the index handler inlines the root's depth-1 rows (capped at 200, unfiltered only) and loadTree paints them before its fetch. Measured on 300k, median of three cold loads: first_row_ms 1,604ms -> 242ms, non-overlapping, and first_row_ms now tracks dcl_ms almost exactly. Main-thread blocking 268ms -> 65ms. Cost 34 KB. exp-004."
---
first_row_ms = DCL + loadTree today; the index handler can embed root depth-1 entries as inline JSON (warm index, or one synchronous scandir <10ms) and the client renders at DCL, reconciling when /api/tree lands. Inline only the unfiltered default view so filter state cannot diverge. Independent of mb-vki5: removes the slow request from the critical path even if it stays slow. Predicted: first_row_ms ~ FCP+render in both scan regimes.
