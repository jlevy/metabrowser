---
type: is
id: is-01ky070wk6z56ghjc9wyhf0sye
title: Unified filtering across navigation and folder views
kind: epic
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-07-20-unified-filtering.md
labels: []
dependencies: []
child_order_hints:
  - is-01ky071d4nwgt5x4920xe0y60e
  - is-01ky071dj04cfxc3gdq6z74xe0
  - is-01ky071dz7zqcfxgxf97pc9vfn
created_at: 2026-07-20T16:51:20.795Z
updated_at: 2026-08-01T05:13:10.424Z
---
Phase 1 is implemented and validated: shared FilterState and mb.filters, Current/Recent chips, age/type/visibility menu, mounted-row dimming, hidden-gitignored pruning, inventory-change reapplication, and treemap state sharing. Phase 2 owns complete hide mode: canonical logical extensions, filtered rollup aggregates, scalable-search integration, scoped-safe deep-change invalidation, and missing nav DOM coverage. Phase 3 retires the Recent tab only after the documented parity gate.

## Notes

2026-07-31 spec status reconciled with code and closed Phase 1 bead mb-1zaq. The spec now rejects loaded-rows-only hide semantics, records compressed logical-extension and depth-two event-scope seams, and treats /api/search as a planned dependency rather than an existing endpoint.
