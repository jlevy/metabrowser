---
type: is
id: is-01kxnx9waq2h69ey9kb0mcg5hq
title: Quick file finder and search providers
kind: feature
status: open
priority: 2
version: 15
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels:
  - search
  - scalability
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
child_order_hints:
  - is-01kyxyb67v18br7jm7w8mrwss5
  - is-01kyxybpctnfvcbj8eh629hab0
  - is-01kyxybvqnw3fmmzhs3hnqhtxr
  - is-01kzmnyznydb254wv11evz3r79
created_at: 2026-07-16T16:49:05.366Z
updated_at: 2026-11-14T18:46:41.609Z
extensions:
  linear:
    id: d2579248-d47f-40b5-b4d8-79ff0a9d7dcb
    linked_at: 2026-08-16T08:05:59.413Z
---
Provider-based search surface, in phases (plan-2026-07-17-scalable-file-search.md). Phase 1, a T or / Quick Search palette that fuzzy-matches a client file catalog without a search request, and Phase 2, a client-complete catalog over non-gitignored filenames (/api/catalog plus catalog.change, decision mb-ci04), shipped in v0.3.0. Repository PR completions joined it with #309 and #314.

Remaining: bounded full-text search (mb-wzy6), and the deferred server filename fallback for roots whose non-ignored file count makes client-complete unreasonable (mb-3arq). Quick Search and content queries stay separate from persisted FilterState and from hierarchical hide-mode filtering.

## Notes

Status 2026-08-08: Phase 1 (client-only palette) and Phase 2 (client-complete catalog feed, redefined per decision mb-ci04) are implemented and merged to feat/quick-file-palette — GET /api/catalog + catalog.change companions + capability.update completion + catalog_feed.js, landed in 16678d3 and hardened against review races in 9b6baea (mb-hj78, mb-3tz2 closed). Remaining children: mb-3arq (bounded server filename search) deferred pending beyond-cap evidence; mb-wzy6 (P3 full-text) open. Spec updated in the same commits.
