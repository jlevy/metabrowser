---
type: is
id: is-01m0w3tw2nce2m2q5qq4w4rg9g
title: "PR #74 scope audit S16: compute filtered newest time from regular files"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:25:45.676Z
updated_at: 2026-08-25T09:25:51.204Z
---
_filtered_tree_projection updates directory newest_mtime_ns for every matched leaf, including symlinks, and uses integer zero as the no-file sentinel. The architecture defines newest time as the maximum descendant regular-file mtime, and epoch zero is valid. Use named optional totals state and add a symlink plus epoch-zero regression test. Evidence: src/metabrowser/inventory_engine/providers/python_inventory.py _filtered_tree_projection.
