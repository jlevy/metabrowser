---
type: is
id: is-01m0t6599kzwr2h009ryfhhffr
title: Replay provider refactor across upstream source changes
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0t65jh124sz9ybqkvnqjdn5
  - type: blocks
    target: is-01m0t65jhkhac6432f3jbmxzwe
  - type: blocks
    target: is-01m0t65jjct33hrw3k3z2v74sf
parent_id: is-01m0t5yhbk3cds1j6x33pvaf26
created_at: 2026-08-24T15:27:55.186Z
updated_at: 2026-08-24T15:32:09.627Z
closed_at: 2026-08-24T15:32:09.626Z
close_reason: All seven provider-refactor commits replayed onto PR 73; source conflicts resolved and the obsolete inventory.py bridge is deleted by the final migration commit.
resolution: null
duplicate_of: null
---
Resolve the seven-commit rebase structurally. Reconcile src/metabrowser/inventory.py deletion with src/metabrowser/inventory_engine/providers/python.py and PythonInventoryHandle; preserve contract, rollup, walker, initial-tree, and startup behavior; leave no speculative InventoryIndex compatibility module.
