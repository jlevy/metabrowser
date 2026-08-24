---
type: is
id: is-01m0rbqsb3e5ep9c328y6ybk4z
title: Delete the singleton and enforce the provider boundary
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqspkv8et5wzmchk9c5mv
  - type: blocks
    target: is-01m0rbqt1448pdt09sadn5xdpa
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:55.458Z
updated_at: 2026-08-24T01:21:08.615Z
closed_at: 2026-08-24T01:21:08.614Z
close_reason: null
resolution: null
duplicate_of: null
---
Files: delete obsolete src/metabrowser/inventory.py ownership exports after migration; update all production imports and tests/conftest.py; add tests/test_inventory_provider_ownership.py and public-hygiene checks. Functions and checks: remove get_instance, reset_instance_for_tests, InventoryIndex, route-level revision sampling, concrete-provider imports outside factory/provider tests, direct event subscription and duplicate walker/index paths. Use app.state or explicit arguments for every consumer. Acceptance: rg and a structural AST/source test prove routes, tree/recent helpers, watcher, activity, SSE and CLI do not import the concrete provider; no compatibility aliases remain; every root has one authoritative handle.
