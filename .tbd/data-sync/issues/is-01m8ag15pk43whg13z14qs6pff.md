---
type: is
id: is-01m8ag15pk43whg13z14qs6pff
title: Guided Review moves and renders late; its first paint must be its final layout
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T23:18:09.864Z
updated_at: 2026-11-25T23:31:47.343Z
started_at: 2026-11-25T23:18:50.469Z
---
User report 2026-11-25: Guided Review parts render slowly and in a delayed way, drawn by JavaScript after the tab opens, unlike other parts of the UI. Suspected chain: on-demand module load when the tab opens, then the guided-review route per step (server renders notes via the KPress child, which can be busy), then the diff plugin's rendered-file route and patches per reference, each with its own loading state. Measure each hop in Chrome, then fix properly: prefetch tier, one step payload, warm renderer, adjacent-step prefetch, first paint equals final layout.

## Notes

User 2026-11-25: 'it is not just delay it is movement during render, which we should not have.' Requirement: nothing moves from first paint, on opening the tab and on each step, cold and warm; pinned by a frame-sampled check.
