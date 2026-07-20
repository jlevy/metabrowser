---
type: is
id: is-01kxz30bt3pby5ffkevch7bgkt
title: "P2: InventoryIndex.rollup query with budgets"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz30c541p7r1sezr4dt4g78
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:21:54.882Z
updated_at: 2026-07-20T06:22:30.562Z
---
inventory.py: rollup(path, *, depth, top, ext_top) -> dict|None; one pass over _entries building children_by_parent (pattern: _build_inventory_tree); recursive aggregation of full-subtree total_files/total_size + unignored_files/unignored_size (parent_ignored propagation), newest mtime (tree contract), state pending/complete from stored total_files, dominant_ext; children mixed dirs+files sorted by bytes desc, top-N emitted, remainder to rest bucket; children:null sentinel past depth with full-subtree totals; envelope-level ext_tallies (top ext_top by bytes + remainder row). Budget gates in tests: <=150ms CPU and <=128KiB pre-gzip at defaults on synthetic 100k-entry index; escape hatch is generation-keyed adjacency cache (spec decision 5). Tests: tests/test_browser_rollup.py with deterministic fixtures (partial, truncated, gitignored, symlinked, moved, deleted).
