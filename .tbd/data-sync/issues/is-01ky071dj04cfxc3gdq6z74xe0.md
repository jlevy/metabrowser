---
type: is
id: is-01ky071dj04cfxc3gdq6z74xe0
title: "P2: complete filter hide mode across nav and folder views"
kind: task
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-07-20-unified-filtering.md
labels: []
dependencies:
  - type: blocks
    target: is-01ky071dz7zqcfxgxf97pc9vfn
parent_id: is-01ky070wk6z56ghjc9wyhf0sye
created_at: 2026-07-20T16:51:38.175Z
updated_at: 2026-08-01T05:13:20.811Z
---
Phase 2 delivers complete server-backed hide mode. Normalize canonical logical extensions across inventory and browser classification; add filtered InventoryIndex.rollup accumulators and /api/rollup validation with max_age_seconds plus repeated exact ext values; remeasure adversarial budgets; bind treemap hide-mode relayout and refetch; add the shared mode control; and integrate nav hide with the bounded /api/search contract in mb-qlsx. Loaded-rows-only hide semantics are explicitly rejected because they cannot report unmounted matches honestly.

## Notes

2026-07-31 plan refinement: treemap visibility sharing and dim-mode age/type behavior already landed in Phase 1. Remaining Phase 2 starts with canonical logical extensions, then filtered rollups using max_age_seconds plus repeated exact ext values, and complete nav hide mode via mb-qlsx. Do not ship loaded-rows-only hide semantics because unmounted matches would be indistinguishable from no match.
