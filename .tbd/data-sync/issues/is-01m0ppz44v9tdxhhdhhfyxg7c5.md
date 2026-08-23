---
type: is
id: is-01m0ppz44v9tdxhhdhhfyxg7c5
title: "H56: first_row_ms rewards painting something early and is indifferent to what follows"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T07:04:41.370Z
updated_at: 2026-08-23T07:20:04.702Z
---
The loop's primary metric measures time to the FIRST visual state and says nothing about how many states follow. exp-010 shows what that bought: first_row_ms 1,473ms to 276 while tree_region_repaints went 1 to 3. The campaign optimised time-to-first-paint and paid in visual states, which is the mechanism of flicker -- placeholder, then replace.

The objective should be: what the reader can see reaches its final state in a single paint, and everything below the fold may arrive later provided it moves nothing above it. Off-screen filling is free; on-screen replacement is not.

Proposed metric: visual_states -- the number of distinct painted layouts of the viewport between navigation and settle, target 1 -- plus time_to_final_state alongside it. tree_region_repaints is today's partial proxy and covers one region only.

Blocked in practice by H51: a metric about painting cannot be validated in a pane that is never visible.
