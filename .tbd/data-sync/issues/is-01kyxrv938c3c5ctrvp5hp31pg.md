---
type: is
id: is-01kyxrv938c3c5ctrvp5hp31pg
title: Repaint plugin charts when the app theme changes
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-01T04:20:49.894Z
updated_at: 2026-08-01T04:20:49.894Z
---
Split from mb-cq5z during PR #19 review R5. src/metabrowser/static/plugin_sdk.js constructs Chart.js canvases from current CSS tokens once, but existing charts do not repaint when the root theme changes. Add a disposal-safe theme-change path and tests for lazy mounting and replacement.
