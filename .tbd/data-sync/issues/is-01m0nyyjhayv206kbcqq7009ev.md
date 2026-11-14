---
type: is
id: is-01m0nyyjhayv206kbcqq7009ev
title: "H42: client-side tree replica in IndexedDB, painted before the server answers"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:57.514Z
updated_at: 2026-11-14T18:43:10.708Z
---
Load-time hypothesis H42 (plan-2026-08-21-load-time-performance.md, Hypotheses). A client-side tree replica in IndexedDB, painted before the server answers, makes a revisit cost no network on the critical path. Metric: first_row_ms on a revisit, offline. The browser-side counterpart to H21 (mb-omhf).
