---
type: is
id: is-01m0w3tw2nce2m2q5qq4w4rg9g
title: "PR #74 scope audit S16: compute filtered newest time from regular files"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:25:45.676Z
updated_at: 2026-08-25T09:57:01.045Z
closed_at: 2026-08-25T09:57:01.045Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
_filtered_tree_projection updates directory newest_mtime_ns for every matched leaf, including symlinks, and uses integer zero as the no-file sentinel. The architecture defines newest time as the maximum descendant regular-file mtime, and epoch zero is valid. Use named optional totals state and add a symlink plus epoch-zero regression test. Evidence: src/metabrowser/inventory_engine/providers/python_inventory.py _filtered_tree_projection.
