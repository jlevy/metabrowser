---
type: is
id: is-01m0ppz44v9tdxhhdhhfyxg7c5
title: "H56: first_row_ms rewards painting something early and is indifferent to what follows"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T07:04:41.370Z
updated_at: 2026-11-14T18:47:01.861Z
---
The loop's primary metric measures time to the first visual state and says nothing about how many states follow. exp-010 shows what that bought: first_row_ms went from 1,473 ms to 276 while tree_region_repaints grew. The campaign optimised time to first paint and paid in visual states, which is the mechanism of flicker: placeholder, then replace.

The objective: what the reader can see reaches its final state in a single paint, and everything below the fold may arrive later provided it moves nothing above it. Off-screen filling is free; on-screen replacement is not.

Proposed metric: visual_states, the number of distinct painted layouts of the viewport between navigation and settle, target 1, with time_to_final_state beside it. It covers the preview pane and filter bar as well as the tree. tree_region_repaints covers one region (fixed at 1 by H11 and H53 in exp-014); the transitions recorder (#373) counts blank frames and region movement per transition, which are related but not this count.

H51 is complete (exp-014, mb-qf2p), so a visible window is available; what remains is the instrument.
