---
type: is
id: is-01m24prkbajqpa7hj9km2yts1n
title: Fix free-threaded inventory and rollup concurrency failures
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01m24nhxxpkrb7cvgyvtxb5d0r
parent_id: is-01m24nhxxpkrb7cvgyvtxb5d0r
created_at: 2026-09-10T03:46:11.423Z
updated_at: 2026-09-10T17:49:01.732Z
closed_at: 2026-09-10T17:49:01.731Z
close_reason: "Completed on codex/release-hardening: coherent optimistic rollup reads, one immutable fallback, coalescing stabilization, and watcher lifecycle fixes all have deterministic regressions. The exact 632f74bc make verify run passed 1,917 tests under CPython 3.14.7t."
resolution: null
duplicate_of: null
---
The local make verify gate on CPython 3.14.7+freethreaded produced four failures: /api/rollup can HTTP 500 with KeyError when live child topology changes between aggregation and emission; simultaneous identical rollups can compute twice; watcher/catalog live-event tests also failed intermittently. Make the inventory read boundary coherent without restoring O(index) request copies, add deterministic regression coverage, and verify both standard and free-threaded Python.
