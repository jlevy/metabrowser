---
type: is
id: is-01m84fn9xvp53f535cfk3qd9cy
title: "Treemap: measure how headers and frames distort area comparisons across folders"
kind: task
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T15:16:14.394Z
updated_at: 2026-11-23T16:59:33.227Z
started_at: 2026-11-23T16:59:33.226Z
---
A folder's header strip and frame come out of its own area before its children are laid out, so a file in a small or deeply nested folder draws smaller than a file of the same size in a large, shallow one. Measure it on a real repository (each file cell's share of the map's area against its share of the total), and decide whether the layout should compensate, for example by sizing each folder for its value plus its header and frame. Asked about in manual testing.

## Notes

Measured 2026-11-23 on this repository's rollup (nodes=max, ignored=exclude, outer box) laid out at 1100x560 by the stack's treemap-layout.js. For each file cell: its share of the map's area over its share of the folder's value (1.00 = true size). Bytes, 1,822 file cells: median 0.74, p10 0.41, p90 0.87. Median by depth: 0.93 at depth 1, 0.87 at 2, 0.74 at 3, 0.64 at 4, 0.42 at 5, 0.29 at 6. Files measure: median 0.73, and 0.12 at depth 8. So headers and frames shrink a deep file to under half the area of an equal shallow one. Siblings within one folder still compare exactly. Options: size each folder for its value plus its header and frame (needs the chrome before the geometry, so iterate or estimate), drop headers below a depth, or accept it and say so in the tooltip or docs. Waiting on the user's choice.
