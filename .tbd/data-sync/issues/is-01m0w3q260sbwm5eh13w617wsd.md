---
type: is
id: is-01m0w3q260sbwm5eh13w617wsd
title: "PR #74 scope audit S14: use an empty checkpoint on coordinator open"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:23:40.863Z
updated_at: 2026-08-25T09:23:45.304Z
---
InventoryCoordinator._replace_root_locked requests DiagnosticsQuery only to obtain version/cursor/state, then discards the projection. The contract defines ReadRequest() as the constant-work checkpoint specifically to avoid a diagnostics dependency. Remove the dummy query/id/import and cover open with the existing coordinator/contract tests. Evidence: src/metabrowser/inventory_engine/coordinator.py _replace_root_locked.
