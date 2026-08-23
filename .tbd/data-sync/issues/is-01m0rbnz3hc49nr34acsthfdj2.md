---
type: is
id: is-01m0rbnz3hc49nr34acsthfdj2
title: Freeze the inventory provider architecture and contract
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqpga27g7sz5v7rs29mbf
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:25:55.824Z
updated_at: 2026-08-23T22:42:55.991Z
closed_at: 2026-08-23T22:42:55.990Z
close_reason: Implemented and verified the sealed provider contract, query registry, lifecycle and bounds, architecture registration, and contract tests.
---
Files: add docs/project/architecture/arch-inventory-provider.md; register it in docs/project/architecture/arch-views-models-routes.md; add src/metabrowser/inventory_engine/__init__.py and contract.py; add tests/test_inventory_provider_contract.py and the registered-surface check. Functions and types: define InventoryBackend.open, InventoryHandle.read/changes/refresh/prioritize/close, InventoryConfig, lifecycle and coverage state, EngineVersion, ChangeCursor, bounded query records for entry, directory, filtered tree, rollup, navigation, recent, catalog, metadata and diagnostics, ReadResult, ChangeBatch, RefreshRequest/Receipt, PriorityRequest, work counters and typed issues. Acceptance: the query vocabulary is closed and provider-neutral; every bound and state transition is documented and mechanically tested; no HTTP, SSE, fdu or concrete Python type crosses the contract.
