---
type: is
id: is-01m0t65jh124sz9ybqkvnqjdn5
title: Port cooperative walker scheduling into Python provider
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies:
  - type: blocks
    target: is-01m0t65vgar07vys3fqmqnd0t5
parent_id: is-01m0t5yhbk3cds1j6x33pvaf26
created_at: 2026-08-24T15:28:04.639Z
updated_at: 2026-08-24T15:32:44.075Z
closed_at: 2026-08-24T15:32:44.058Z
close_reason: Ported the measured 64-entry cooperative yield into PythonInventoryHandle._run_walker and migrated the upstream interleaving test; focused startup tests pass.
resolution: null
duplicate_of: null
---
Carry PR 73 responsiveness semantics into src/metabrowser/inventory_engine/providers/python.py: PythonInventoryHandle._run_walker must yield to request tasks every measured 64 input entries independently of WALKER_EMIT_BATCH. Preserve the measurement rationale and migrate test_inventory_walker_yields_to_request_tasks_between_entry_batches in tests/test_startup_nonblocking.py.
