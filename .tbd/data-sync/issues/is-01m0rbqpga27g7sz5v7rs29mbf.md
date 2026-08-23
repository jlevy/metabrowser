---
type: is
id: is-01m0rbqpga27g7sz5v7rs29mbf
title: Extract the Python reference provider
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqpvchne5gpw8bsmzt5bq
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:52.551Z
updated_at: 2026-08-23T23:25:00.909Z
closed_at: 2026-08-23T23:25:00.908Z
close_reason: Extracted the retained Python engine into PythonInventoryHandle, implemented every provider query and command, bounded resumable changes, coherent state/version capture, semantic walker records, and provider contract tests; make verify passes.
resolution: null
duplicate_of: null
---
Files: relocate the stateful implementation from src/metabrowser/inventory.py into src/metabrowser/inventory_engine/providers/python.py with providers/__init__.py; update src/metabrowser/walker.py, inventory_rollup.py and events.py so provider semantic entries are distinct from browser wire events; migrate focused tests from InventoryIndex to PythonInventoryHandle. Functions: preserve the current BFS walker, incremental child indexes, aggregate caches, navigation tally memo, generation conflict handling, subtree refresh and diagnostics while implementing InventoryHandle.read, changes, refresh, prioritize and close. Add coherent state/version/cursor capture, bounded resumable ChangeBatch history and prompt task cancellation. Acceptance: existing walker, mutation, rollup, truncation, symlink, gitignore and concurrency tests pass unchanged in behavior; no fdu dependency or runtime placeholder exists; PythonInventoryHandle is the only retained filesystem owner for an opened root.
