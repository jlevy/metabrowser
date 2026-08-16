---
type: is
id: is-01ky071dj04cfxc3gdq6z74xe0
title: "P2: complete filter hide mode across nav and folder views"
kind: task
status: open
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-07-20-unified-filtering.md
labels: []
dependencies:
  - type: blocks
    target: is-01ky071dz7zqcfxgxf97pc9vfn
parent_id: is-01ky070wk6z56ghjc9wyhf0sye
created_at: 2026-07-20T16:51:38.175Z
updated_at: 2026-08-16T08:06:37.590Z
extensions:
  linear:
    id: a686753d-cd6a-468c-b561-ea7336b89acd
    linked_at: 2026-08-16T08:06:37.590Z
---
Phase 2 delivers complete server-backed hide mode. Normalize logical extensions across inventory and browser classification; add filtered InventoryIndex.rollup accumulators and /api/rollup validation; add a dedicated /api/filter/tree hierarchy with public revision and scoped-safe invalidation; remeasure adversarial budgets; bind treemap hide-mode relayout and nav hide behavior; and add missing DOM coverage. Do not reuse flat filename or full-text search endpoints for filter projection.

## Notes

2026-07-31 search architecture review separated transient discovery from persisted filters. This task owns the hierarchical /api/filter/tree contract. Quick file uses /api/search/files only in its later server phase; full text uses /api/search/text.
