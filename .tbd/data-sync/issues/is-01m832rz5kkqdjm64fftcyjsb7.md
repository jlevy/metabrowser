---
type: is
id: is-01m832rz5kkqdjm64fftcyjsb7
title: "Treemap: extract the map component, fix edge containment, nest deeper"
kind: task
status: in_progress
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/723
    at: 2026-11-23T02:52:13.443Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T02:11:48.526Z
updated_at: 2026-11-23T02:52:13.446Z
started_at: 2026-11-23T02:12:07.170Z
---
Extract treemap-map.js from treemap.js; lay out to the padding box so edge cells sit inside the border; nest as deep as cells have room, framing folders too small for a label; spread the cell budget by area; request the rollup's maximum depth and width (export ROLLUP_MAX_DEPTH and ROLLUP_MAX_TOP to the browser). Stack layer 2.
