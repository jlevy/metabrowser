---
type: is
id: is-01m849sm0qja52cpa08ea7p6r9
title: Treemap view lays the map out twice on first paint
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
created_at: 2026-11-23T13:33:44.341Z
updated_at: 2026-11-23T13:33:44.341Z
---
Found by the WebKit gate's treemap case (apps/macos/webkit-gate, treemap-100k) on 2026-11-23, in both engines: the viewport is 415-416 px tall when the labels mount and 392-393 px a frame later, so the ResizeObserver in builtin_plugins/folder/treemap.js lays all cells out again. At PAINT_MAX_CELLS (25,000 cells) that second layout is most of the ~110 ms between the first forced layout and the next frame. Find which row above the map grows after the first layout (the legend row's entries arriving, the totals bars, or the status line), keep its box from the start (docs/design-system.md, Regions Keep Their Boxes), and add a check that a first paint lays out once. Also explain the metric switch's cost beyond the layout: Bytes measured 1.21-1.38x Chrome in WebKit in that run.
