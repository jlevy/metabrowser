---
type: is
id: is-01m83r0j5x920yvdc3hrnevzvy
title: "Treemap WebKit gate case: set PAINT_MAX_CELLS from WKWebView"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
created_at: 2026-11-23T08:22:57.463Z
updated_at: 2026-11-23T08:22:57.463Z
---
Layer 5 of the treemap canvas plan (docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md). Add a treemap case to apps/macos/webkit-gate/run.mjs and probe.js: a synthetic folder of ~100k files, the Treemap tab, timing first paint, a metric switch's relayout and repaint, and a family hover's mark ops, at the raised ROLLUP_MAX_NODES. Set PAINT_MAX_CELLS (treemap-map.js) from both engines, with the measurement beside the constant. Deferred from layer 4 because the 4,000-node rollup keeps layer 4's map near 4k cells, well under the bound, which Chrome paints in 7 ms.
