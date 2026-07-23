---
type: is
id: is-01ky071dj04cfxc3gdq6z74xe0
title: "P2: folder views on shared filter state and filtered rollups"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-unified-filtering.md
labels: []
dependencies:
  - type: blocks
    target: is-01ky071dz7zqcfxgxf97pc9vfn
parent_id: is-01ky070wk6z56ghjc9wyhf0sye
created_at: 2026-07-20T16:51:38.175Z
updated_at: 2026-07-23T22:28:38.259Z
---
Phase 2, hide mode with completeness: InventoryIndex.rollup grows filtered accumulator sets (age_max_s + types params, generalizing the unignored_* dual accumulators) with filtered_files/filtered_size on nodes + filtered ext tally column; /api/rollup param validation + wire validators; adversarial budget re-measured with filters active; treemap hide-mode relayout weights + watchRollup refetch on hide-value changes; a mode switch appears in the shared menu only when this lands; nav hide waits on /api/search (or ships pruned loaded-rows-only semantics with an explicit incompleteness note — open review question).
