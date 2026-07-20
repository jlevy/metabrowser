---
type: is
id: is-01ky071dj04cfxc3gdq6z74xe0
title: "P2: folder views on shared filter state and filtered rollups"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-unified-filtering.md
labels: []
dependencies:
  - type: blocks
    target: is-01ky071dz7zqcfxgxf97pc9vfn
parent_id: is-01ky070wk6z56ghjc9wyhf0sye
created_at: 2026-07-20T16:51:38.175Z
updated_at: 2026-07-20T16:51:50.517Z
---
Migrate the treemap ignored control from metabrowser.folder.treemap localStorage to mb.filters (one-time key migration); bind age/type dim mode to cells. InventoryIndex.rollup gains age_max_s + types filtered aggregate variants (generalizing the unignored_* dual accumulators, one filtered set per request); /api/rollup params + wire validators (filtered_files/filtered_size); hide-mode relayout + watchRollup refetch on filter change; re-measure the rollup budget with filters active. Nav hide mode via /api/search with empty keyword once the scalable-search endpoint lands (falls back to dim until then — cross-reference plan-2026-07-17-scalable-file-search.md).
