---
type: is
id: is-01kzyh19v1gfs0r35wkmmd7j3n
title: "PR #37 review F1: Bound and offload rollup request work"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:14.912Z
updated_at: 2026-08-13T21:53:01.230Z
closed_at: 2026-08-13T21:53:01.226Z
close_reason: "Fixed: /api/rollup now offloads to a worker and reuses an immutable child index cached per inventory generation; regression tests cover thread affinity, reuse, and invalidation."
---
F1 High at src/metabrowser/server.py:1186 and src/metabrowser/inventory_rollup.py:98. /api/rollup performs whole-inventory synchronous aggregation on the event loop. Offload the request work and scope repeated aggregation cost so a leaf-folder rollup does not rebuild a child index from every inventory entry.
