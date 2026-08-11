---
type: is
id: is-01kxry1shrk3exgwm30k257tca
title: "Review D3: research doc missing comparison state-model decision (self-describing IDs, bounded manifest cache)"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T20:59:52.248Z
updated_at: 2026-07-17T21:04:55.518Z
closed_at: 2026-07-17T21:04:55.518Z
close_reason: "Addressed in commit cc92da0 on the diff-research branch: platform prerequisites section + Phase 0 fold-in, packaging-reality paragraph, self-describing comparison IDs, git adapter safety additions, tool-surface and tree-decoration open decisions, docs-tree conventions in development.md. make verify green (705 tests)."
---
POST /comparisons implies server-held session state with TTL/eviction; recommend self-describing deterministic comparison IDs so GETs can rebuild evicted comparisons; bounded LRU of materialized manifests.
