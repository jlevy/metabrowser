---
type: is
id: is-01m0qyzmmmym17nxw6m7964xcp
title: Make rollup payload and ETag revision atomic
kind: bug
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - correctness
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqqw9a3dv398mhqhzw93h
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T18:44:01.298Z
updated_at: 2026-08-24T00:49:12.820Z
closed_at: 2026-08-24T00:49:12.819Z
close_reason: Rollup payload, engine version and cursor are captured atomically; route ETags and body keys derive from that result, and forced mid-projection mutation proves old body/old ETag followed by new body/new ETag.
resolution: null
duplicate_of: null
---
Files: src/metabrowser/inventory_engine/providers/python.py coherent rollup read path, src/metabrowser/server.py api_rollup validator/body cache integration, and tests/test_rollup_route.py concurrent-write regression. Functions: replace the current rollup_revision then off-thread rollup split with a RollupQuery result that captures payload, status, engine version and cursor atomically using version-check/retry or an immutable snapshot fallback; derive the host ETag only from that returned result and canonical request/root/build identity. Acceptance: a forced write between projection work and response construction cannot pair an old ETag with a newer body, aggregate memo reuse remains safe, and cached/304 behavior is preserved.
