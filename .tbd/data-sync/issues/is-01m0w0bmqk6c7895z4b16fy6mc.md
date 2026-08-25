---
type: is
id: is-01m0w0bmqk6c7895z4b16fy6mc
title: "PR #74 scope audit S1: remove superseded Python-only filtered-tree pipeline"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:25:00.914Z
updated_at: 2026-08-25T08:25:00.914Z
---
Production tree, CLI, and snapshot consumers now use provider-owned FilteredTreeQuery. Delete the unreferenced build_filtered_inventory_tree/DirMatches/filtered_rollups/cache path and its parallel semantic tests; retain only TreeFilter parsing and provider projection tests. Update comments and docs to point at the provider contract.
