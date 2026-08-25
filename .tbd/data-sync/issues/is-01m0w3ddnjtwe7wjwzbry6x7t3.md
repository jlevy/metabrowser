---
type: is
id: is-01m0w3ddnjtwe7wjwzbry6x7t3
title: "PR #74 scope audit S11: preserve pre-epoch mtimes in catalog records"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:18:24.945Z
updated_at: 2026-08-25T09:18:29.566Z
---
CatalogRecord.__post_init__ rejects negative mtime_ns even though InventoryEntry and real filesystem metadata permit pre-1970 timestamps. This introduces a provider-boundary regression for catalog/activity reads. Remove the inconsistent restriction and pin the edge case in the contract tests. Evidence: src/metabrowser/inventory_engine/contract.py CatalogRecord.
