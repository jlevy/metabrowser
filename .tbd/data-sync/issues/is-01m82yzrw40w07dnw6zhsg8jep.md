---
type: is
id: is-01m82yzrw40w07dnw6zhsg8jep
title: "Treemap: deeper nesting, containment fix, compact map on Overview"
kind: feature
status: in_progress
priority: 2
version: 11
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/722
    at: 2026-11-23T02:52:15.430Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/723
    at: 2026-11-23T02:52:15.907Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/724
    at: 2026-11-23T02:52:16.428Z
delegate: claude-code@spud10
labels: []
dependencies: []
child_order_hints:
  - is-01m832rs4ryhw09n31ah5haztf
  - is-01m832rz5kkqdjm64fftcyjsb7
  - is-01m832s53eb7m4chdhzwncqt3r
hold: null
hold_until: null
created_at: 2026-11-23T01:05:37.128Z
updated_at: 2026-11-23T02:52:16.429Z
started_at: 2026-11-23T01:05:57.669Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
---
The Treemap drew two levels, laid out to the viewport's border box so right and bottom edge cells were clipped, and the rollup's breadth-first node budget left large folders unexpanded. Nest as deep as cells have room (framed nesting for small folders), spread the cell budget by area, request the rollup's max depth and width with heaviest-first emission, fix the drawable box, and extract the map into a component also drawn compactly under File Overview.
