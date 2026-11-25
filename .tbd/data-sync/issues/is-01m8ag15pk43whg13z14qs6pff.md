---
type: is
id: is-01m8ag15pk43whg13z14qs6pff
title: Guided Review renders late, in visible steps, unlike the rest of the UI
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T23:18:09.864Z
updated_at: 2026-11-25T23:18:09.864Z
---
User report 2026-11-25: Guided Review parts render slowly and in a delayed way, drawn by JavaScript after the tab opens, unlike other parts of the UI. Suspected chain: on-demand module load when the tab opens, then the guided-review route per step (server renders notes via the KPress child, which can be busy), then the diff plugin's rendered-file route and patches per reference, each with its own loading state. Measure each hop in Chrome, then fix properly: prefetch tier, one step payload, warm renderer, adjacent-step prefetch, first paint equals final layout.
