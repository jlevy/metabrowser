---
type: is
id: is-01m0m5vxnbtymm7d8pq4f0nwbr
title: Encoded-body cache and validator for /api/tree (H25)
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T07:27:21.770Z
updated_at: 2026-11-14T18:42:42.894Z
---
/api/rollup keeps an ETag-keyed encoded-body cache; /api/tree re-serializes and re-gzips an unchanged answer per poller and per tab. Same (revision, params)-keyed cache + 304 validator. Batch with mb-vki5 — same handler. Settled root tree ~15ms -> ~1ms.

## Notes

2026-11-14 audit: mb-vki5 is closed, so there is nothing to batch with; H45 (mb-0l4a) is the remaining neighbour on the same handler.
