---
type: is
id: is-01m0r1a87ja8zc0p9kjv5m94fq
title: "PR #73 review R6: bound always-on responsiveness storage"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0r191gatek6ffx1e50wmgr8
created_at: 2026-08-23T19:24:46.193Z
updated_at: 2026-08-23T21:34:06.928Z
closed_at: 2026-08-23T21:34:06.927Z
close_reason: Always-on telemetry now uses bounded detail rings and bounded label cardinality while preserving exact whole-window counts, totals, maxima, and overflow signals, with tests.
---
PR #73. src/metabrowser/static/perf.js appends long-task and interaction samples for the whole packaged session. Bound detail storage and preserve bounded aggregates or gate full profiling explicitly. Review: https://github.com/jlevy/metabrowser/pull/73#pullrequestreview-5003175212
