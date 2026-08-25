---
type: is
id: is-01m0w3q260sbwm5eh13w617wsd
title: "PR #74 scope audit S14: use an empty checkpoint on coordinator open"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:23:40.863Z
updated_at: 2026-08-25T09:57:01.039Z
closed_at: 2026-08-25T09:57:01.039Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
InventoryCoordinator._replace_root_locked requests DiagnosticsQuery only to obtain version/cursor/state, then discards the projection. The contract defines ReadRequest() as the constant-work checkpoint specifically to avoid a diagnostics dependency. Remove the dummy query/id/import and cover open with the existing coordinator/contract tests. Evidence: src/metabrowser/inventory_engine/coordinator.py _replace_root_locked.
