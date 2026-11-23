---
type: is
id: is-01m82yzrw40w07dnw6zhsg8jep
title: "Treemap: deeper nesting, containment fix, compact map on Overview"
kind: feature
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T01:05:37.128Z
updated_at: 2026-11-23T01:26:47.201Z
started_at: 2026-11-23T01:05:57.669Z
closed_at: 2026-11-23T01:26:47.199Z
close_reason: null
resolution: null
duplicate_of: null
---
The Treemap drew two levels, laid out to the viewport's border box so right and bottom edge cells were clipped, and the rollup's breadth-first node budget left large folders unexpanded. Nest as deep as cells have room (framed nesting for small folders), spread the cell budget by area, request the rollup's max depth and width with heaviest-first emission, fix the drawable box, and extract the map into a component also drawn compactly under File Overview.
