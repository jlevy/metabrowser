---
type: is
id: is-01m0w0bmqk6c7895z4b16fy6mc
title: "PR #74 scope audit S1: remove superseded Python-only filtered-tree pipeline"
kind: task
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:25:00.914Z
updated_at: 2026-08-25T09:57:00.979Z
closed_at: 2026-08-25T09:57:00.978Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
Production tree, CLI, and snapshot consumers now use provider-owned FilteredTreeQuery. Delete the unreferenced build_filtered_inventory_tree/DirMatches/filtered_rollups/cache path and its parallel semantic tests; retain only TreeFilter parsing and provider projection tests. Update comments and docs to point at the provider contract.
