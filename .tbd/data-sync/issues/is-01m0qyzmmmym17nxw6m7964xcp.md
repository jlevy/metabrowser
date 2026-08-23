---
type: is
id: is-01m0qyzmmmym17nxw6m7964xcp
title: Make rollup payload and ETag revision atomic
kind: bug
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - correctness
dependencies: []
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T18:44:01.298Z
updated_at: 2026-08-23T21:37:57.746Z
---
The /api/rollup route samples InventoryIndex.rollup_revision() before dispatching a worker build, while InventoryIndex._rollup_view() deliberately exposes live mappings that may observe later writes. The eviction epoch protects the aggregate memo but does not prove the returned body belongs to the ETag revision. Make the query return its atomically captured version (or use an immutable snapshot/version-check retry), then build the ETag from that result. Add a concurrent-write regression test.
