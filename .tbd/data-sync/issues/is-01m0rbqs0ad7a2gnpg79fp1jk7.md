---
type: is
id: is-01m0rbqs0ad7a2gnpg79fp1jk7
title: Move CLI walk and API-check paths off the process singleton
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqsb3e5ep9c328y6ybk4z
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:55.113Z
updated_at: 2026-08-24T00:52:21.306Z
closed_at: 2026-08-24T00:52:21.305Z
close_reason: build_tree_envelope now opens and closes a local InventoryRuntime with caller caps and typed Entry/Directory/FilteredTree reads; repeated asyncio.run JSON/YAML paths pass, check-api already uses app lifespan, and all 48 CLI goldens are byte-stable.
resolution: null
duplicate_of: null
---
Files: refactor src/metabrowser/walk.py, cli/walk_cli.py, cli/check_api.py and their golden/unit tests. Functions: build_tree_envelope must create and close a local Python backend/coordinator with caller caps, issue provider-neutral reads, and never reset process-global state; standalone walk_report may continue to drive the pure walker directly. Ensure repeated asyncio.run calls cannot retain an event bound to an older loop. Acceptance: text, JSON, YAML, JSONL, subtree, filter and check-api goldens are byte-for-byte stable and CLI execution leaves no background inventory task.
