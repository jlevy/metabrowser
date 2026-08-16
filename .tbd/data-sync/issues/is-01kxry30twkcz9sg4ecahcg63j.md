---
type: is
id: is-01kxry30twkcz9sg4ecahcg63j
title: "Platform A1: plugin sub-router mount (path params, full methods, honest status codes)"
kind: feature
status: open
priority: 1
version: 3
labels: []
dependencies:
  - type: blocks
    target: is-01kxse0vfwwkcq1a6mfdx6v9ad
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:32.476Z
updated_at: 2026-08-16T08:05:43.176Z
extensions:
  linear:
    id: 8abea237-409f-4114-b118-4efa20f438b3
    linked_at: 2026-08-16T08:05:43.176Z
---
Data hooks are exact single-segment GET/POST routes with 5xx flattened to 200 (static_assets.py:158-167,214). Diff plugin REST shape needs a Starlette Mount per installed plugin with real status passthrough for ETag/304/Range.
