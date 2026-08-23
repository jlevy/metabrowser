---
type: is
id: is-01m0rbqpvchne5gpw8bsmzt5bq
title: Add the composition root, coordinator and sparse overlay
kind: task
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqq5z7qns1c2jy5pqrk5b
  - type: blocks
    target: is-01m0rbqqw9a3dv398mhqhzw93h
  - type: blocks
    target: is-01m0rbqs0ad7a2gnpg79fp1jk7
  - type: blocks
    target: is-01m0qyzmmmym17nxw6m7964xcp
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:52.907Z
updated_at: 2026-08-23T23:43:29.893Z
closed_at: 2026-08-23T23:43:29.892Z
close_reason: Implemented the sealed Python factory, application-owned runtime, concurrent coordinator lifecycle, sparse overlay, compound host versions, bounded change replay/coalescing/overflow/reset, cache invalidation listeners, and deterministic lifecycle tests; full test suite passes.
resolution: null
duplicate_of: null
---
Files: add src/metabrowser/inventory_engine/factory.py, coordinator.py, overlay.py and runtime.py; add tests/test_inventory_coordinator.py and tests/test_inventory_overlay.py. Functions: make the sealed factory construct PythonInventoryBackend; make InventoryCoordinator open exactly one handle, serialize root replacement, join overlay decorations onto returned entries, derive host versions from engine plus overlay revisions, expose provider-neutral read/refresh/prioritize/close and bounded host-event subscriptions, and centralize cache invalidation. Move active, PID and plugin labels into InventoryOverlay keyed by lossless relative path. Acceptance: a deterministic fake provider proves lifecycle, coherent reads, change coalescing, reset/overflow, root replacement and close; the overlay never changes provider totals or engine versions; adding another provider requires only a factory entry and InventoryHandle implementation.
