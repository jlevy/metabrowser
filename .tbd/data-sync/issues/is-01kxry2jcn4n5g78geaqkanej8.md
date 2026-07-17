---
type: is
id: is-01kxry2jcn4n5g78geaqkanej8
title: "Review C12: no SRI integrity attributes on pinned CDN scripts/styles"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:17.684Z
updated_at: 2026-07-17T21:16:43.650Z
closed_at: 2026-07-17T21:16:43.650Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
Pinned jsdelivr assets (server.py:697-719,807-809) lack integrity= hashes; supply-chain gap at the browser runtime layer; add sha384 SRI + crossorigin and enforce in test_index_cdn_origins.py.
