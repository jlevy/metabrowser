---
type: is
id: is-01kxry31b7bpyxphe66g7gr64t
title: "Platform A3: expose file-change event subscription/emission to installed plugins via plugin_api"
kind: feature
status: open
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01kxse0wddy6je24t1dm5caber
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:32.999Z
updated_at: 2026-08-16T08:06:14.969Z
extensions:
  linear:
    id: 33bb512a-82cb-4713-8dc5-74f8d677d894
    linked_at: 2026-08-16T08:06:14.969Z
---
InventoryIndex.subscribe() and ProjectionInvalidate/Update exist but are not in plugin_api; diff comparisons need watcher-driven invalidation without private imports.
