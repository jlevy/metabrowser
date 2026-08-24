---
type: is
id: is-01m0rbqqw9a3dv398mhqhzw93h
title: Migrate rollups to atomic provider results and validators
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqsb3e5ep9c328y6ybk4z
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:53.960Z
updated_at: 2026-08-24T00:49:13.089Z
closed_at: 2026-08-24T00:49:13.088Z
close_reason: api_rollup uses RollupQuery through the coordinator with version-pinned fallback, shared in-flight builds, aggregate memo reuse, cancellation and cache/304 behavior covered by the provider-neutral rollup suite.
resolution: null
duplicate_of: null
---
Files: refactor src/metabrowser/server.py api_rollup and rollup body cache, src/metabrowser/inventory_rollup.py as needed, and tests/test_rollup_route.py, test_browser_rollup.py and test_inventory_rollup.py. Functions: execute RollupQuery through InventoryCoordinator, return the rollup payload with the exact engine/host version captured for it, derive ETag and retained-body keys only from that result plus request/root/build identity, and retain in-flight request coalescing. Replace live _rollup_view torn reads with version-check/retry or an immutable snapshot fallback while preserving subtree aggregate reuse. Acceptance: File Rollup conformance, bounds, populations, conservation, ranking and cache behavior pass; a forced concurrent write cannot pair an old validator with a new body; settled and scanning performance remain within the recorded baseline noise.
