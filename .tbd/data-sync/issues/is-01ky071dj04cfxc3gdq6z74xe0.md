---
type: is
id: is-01ky071dj04cfxc3gdq6z74xe0
title: "P2: complete filter hide mode across nav and folder views"
kind: task
status: closed
priority: 2
version: 13
spec_path: null
labels: []
dependencies:
  - type: blocks
    target: is-01ky071dz7zqcfxgxf97pc9vfn
parent_id: is-01ky070wk6z56ghjc9wyhf0sye
created_at: 2026-07-20T16:51:38.175Z
updated_at: 2026-11-04T17:14:27.048Z
closed_at: 2026-11-01T16:21:21.927Z
close_reason: filter-state.js on main states there is no dim/hide switch, and /api/filter/tree was never built; TreeFilter on /api/tree replaced this.
resolution: canceled
duplicate_of: null
extensions:
  linear:
    id: a686753d-cd6a-468c-b561-ea7336b89acd
    linked_at: 2026-08-16T08:06:37.590Z
---
Phase 2 delivers complete server-backed hide mode. Normalize logical extensions across inventory and browser classification; add filtered InventoryIndex.rollup accumulators and /api/rollup validation; add a dedicated /api/filter/tree hierarchy with public revision and scoped-safe invalidation; remeasure adversarial budgets; bind treemap hide-mode relayout and nav hide behavior; and add missing DOM coverage. Do not reuse flat filename or full-text search endpoints for filter projection.

## Notes

2026-07-31 search architecture review separated transient discovery from persisted filters. This task owns the hierarchical /api/filter/tree contract. Quick file uses /api/search/files only in its later server phase; full text uses /api/search/text.

Tracking reconciliation: the structured spec_path `docs/project/specs/active/plan-2026-07-20-unified-filtering.md` does not exist in landed main da87bb13c4434324af576b554711278139621b6b. No exact surviving document or immutable historical blob has been established by this audit. Retire this broken structured pointer while preserving this completed task's status, description and implementation/review history. This note retains the former path for historical context; it does not claim that a current plan is the exact successor.
