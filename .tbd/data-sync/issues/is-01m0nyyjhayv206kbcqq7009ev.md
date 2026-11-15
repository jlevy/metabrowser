---
type: is
id: is-01m0nyyjhayv206kbcqq7009ev
title: "H42: client-side tree replica in IndexedDB, painted before the server answers"
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:57.514Z
updated_at: 2026-11-15T06:55:41.674Z
closed_at: 2026-11-15T06:55:41.673Z
close_reason: "H42 retired (architecture review, 2026-11-14): the shell document comes from the process a relaunch waits for, so a client tree replica cannot paint before it. A restored window's first-rows snapshot is native work (mb-54k9)."
resolution: canceled
duplicate_of: null
---
Load-time hypothesis H42 (plan-2026-08-21-load-time-performance.md, Hypotheses). A client-side tree replica in IndexedDB, painted before the server answers, makes a revisit cost no network on the critical path. Metric: first_row_ms on a revisit, offline. The browser-side counterpart to H21 (mb-omhf).
