---
type: is
id: is-01m0w3rj3t1azr6v6z8xf3byt5
title: "PR #74 scope audit S15: remove unused InventoryRuntime backend injection"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:24:29.945Z
updated_at: 2026-08-25T09:24:33.894Z
---
InventoryRuntime.__init__ accepts both provider and backend, silently ignores provider when backend is supplied, and has no caller using backend injection. InventoryCoordinator already owns the explicit backend seam used by tests. Remove the unused argument/import/branch to keep construction sealed and unambiguous. Evidence: src/metabrowser/inventory_engine/runtime.py InventoryRuntime.__init__.
