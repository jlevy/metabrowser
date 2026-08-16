---
type: is
id: is-01ky070wk6z56ghjc9wyhf0sye
title: Unified filtering across navigation and folder views
kind: epic
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-07-20-unified-filtering.md
labels: []
dependencies: []
child_order_hints:
  - is-01ky071d4nwgt5x4920xe0y60e
  - is-01ky071dj04cfxc3gdq6z74xe0
  - is-01ky071dz7zqcfxgxf97pc9vfn
created_at: 2026-07-20T16:51:20.795Z
updated_at: 2026-08-16T08:05:43.277Z
extensions:
  linear:
    id: 2966f32d-9498-4efd-95bb-ee77e5c5d062
    linked_at: 2026-08-16T08:05:43.277Z
---
Phase 1 is implemented and validated: shared FilterState and mb.filters, Current and Recent chips, age/type/visibility menu, mounted-row dimming, hidden-gitignored pruning, inventory-change reapplication, and treemap state sharing. Phase 2 owns complete hide mode through canonical logical extensions, filtered rollup aggregates, a dedicated /api/filter/tree projection, scoped-safe deep-change invalidation, and missing nav DOM coverage. Quick file and full-text search remain transient provider-driven discovery outside FilterState. Phase 3 retires the Recent tab only after the documented parity gate.

## Notes

2026-07-31 search architecture review decoupled hierarchical filtering from search. Hide mode uses /api/filter/tree rather than a search endpoint. The slash-key finder and future full-text mode do not persist, alter filter chips, or dim the tree.
