---
type: is
id: is-01m85f546ddhc098egv5e0ehqg
title: "Treemap: a relayout under a legend hover fades the old layout's lift over the new map"
kind: bug
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
created_at: 2026-11-24T00:26:38.550Z
updated_at: 2026-11-25T02:16:20.156Z
---
Review C1 on PR 767: when a relayout changes a family's marked indexes under a still legend hover, drawCellHover draws on the back canvas and fades the front, which still holds the old layout's pixels, over the new map. Draw the front in place when the hover target is unchanged across a relayout.
