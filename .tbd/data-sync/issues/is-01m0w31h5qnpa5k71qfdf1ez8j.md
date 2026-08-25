---
type: is
id: is-01m0w31h5qnpa5k71qfdf1ez8j
title: "PR #74 scope audit S10: validate provider identity and terminal refresh receipts"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:11:55.304Z
updated_at: 2026-08-25T09:17:04.205Z
---
InventoryCoordinator checked only session identity on reads, changes, and refresh, and did not require RefreshReceipt accepted/rejected paths to cover the request. Enforce immutable session/scope/semantic identity through one shared check on every surface, require exact per-path refresh disposition, bound receipt cardinality, and add failure-path tests. Evidence: src/metabrowser/inventory_engine/coordinator.py _observe_read_locked, _apply_pending_provider_changes, refresh; contract.py RefreshReceipt.
