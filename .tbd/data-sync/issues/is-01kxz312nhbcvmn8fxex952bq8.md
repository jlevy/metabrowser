---
type: is
id: is-01kxz312nhbcvmn8fxex952bq8
title: "P3: treemap_layout.js pure layout module"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz3131cqxh1xc4zdq4x9ss8
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:22:18.288Z
updated_at: 2026-07-20T06:22:32.297Z
---
builtin_plugins/folder/treemap_layout.js as classic script exposing global MetabrowserTreemapLayout (strict check-JS, loaded via extra_scripts before index.js): squarify(items, rect) per Bruls/Huizing/van Wijk; layoutTree(rollupNode, viewport, opts) applying active metric (bytes|files) and grouping (folder hierarchy | ext_tallies one-cell-per-extension), returning positioned cells with nesting depth; culling below opts.minCellPx; opts.maxCells cap (default 800); remainder-cell synthesis from rest buckets and culled children. Golden vm tests tests/test_folder_treemap_layout_js.py: areas sum to rect, aspect quality, culling, remainder, both groupings.
