---
type: is
id: is-01m0w3rj3t1azr6v6z8xf3byt5
title: "PR #74 scope audit S15: remove unused InventoryRuntime backend injection"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:24:29.945Z
updated_at: 2026-08-25T09:57:01.062Z
closed_at: 2026-08-25T09:57:01.062Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
InventoryRuntime.__init__ accepts both provider and backend, silently ignores provider when backend is supplied, and has no caller using backend injection. InventoryCoordinator already owns the explicit backend seam used by tests. Remove the unused argument/import/branch to keep construction sealed and unambiguous. Evidence: src/metabrowser/inventory_engine/runtime.py InventoryRuntime.__init__.
