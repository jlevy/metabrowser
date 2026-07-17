---
type: is
id: is-01kxry1shrk3exgwm30k257tca
title: "Review D3: research doc missing comparison state-model decision (self-describing IDs, bounded manifest cache)"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T20:59:52.248Z
updated_at: 2026-07-17T20:59:52.248Z
---
POST /comparisons implies server-held session state with TTL/eviction; recommend self-describing deterministic comparison IDs so GETs can rebuild evicted comparisons; bounded LRU of materialized manifests.
