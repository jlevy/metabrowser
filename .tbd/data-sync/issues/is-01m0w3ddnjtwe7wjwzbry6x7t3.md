---
type: is
id: is-01m0w3ddnjtwe7wjwzbry6x7t3
title: "PR #74 scope audit S11: preserve pre-epoch mtimes in catalog records"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:18:24.945Z
updated_at: 2026-08-25T09:57:01.020Z
closed_at: 2026-08-25T09:57:01.020Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
CatalogRecord.__post_init__ rejects negative mtime_ns even though InventoryEntry and real filesystem metadata permit pre-1970 timestamps. This introduces a provider-boundary regression for catalog/activity reads. Remove the inconsistent restriction and pin the edge case in the contract tests. Evidence: src/metabrowser/inventory_engine/contract.py CatalogRecord.
