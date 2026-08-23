---
type: is
id: is-01m0r1a7wskv5xdpbwwc4h83xv
title: "PR #73 review R5: make perf reset start a coherent window"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0r191gatek6ffx1e50wmgr8
created_at: 2026-08-23T19:24:45.848Z
updated_at: 2026-08-23T19:24:45.848Z
---
PR #73. src/metabrowser/static/perf.js:623-654 clears numerators but keeps the navigation-time denominator and hidden-state history. Reset the full measurement window and test it. Review: https://github.com/jlevy/metabrowser/pull/73#pullrequestreview-5003175212
