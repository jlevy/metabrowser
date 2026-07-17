---
type: is
id: is-01kxry2jcn4n5g78geaqkanej8
title: "Review C12: no SRI integrity attributes on pinned CDN scripts/styles"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:17.684Z
updated_at: 2026-07-17T21:00:17.684Z
---
Pinned jsdelivr assets (server.py:697-719,807-809) lack integrity= hashes; supply-chain gap at the browser runtime layer; add sha384 SRI + crossorigin and enforce in test_index_cdn_origins.py.
