---
type: is
id: is-01kzfe3a1108snwxx1dh7dtk52
title: Quick File results never refresh as the catalog grows
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-08T00:59:18.432Z
updated_at: 2026-08-08T00:59:18.432Z
---
A search run while the inventory is still loading stays stale after loading finishes, so coverage is permanently incomplete for that query.

- the palette subscribes only to the search controller (search_palette.js), never to catalog changes, and the controller publishes only in response to a keystroke
- known_file_catalog.snapshot() hardcodes complete: false (typed as the literal false), so the status line claims 'Local coverage is incomplete' even once the walker reports status=done

Required behavior: tolerate incomplete results while indexing, then be complete once it finishes. That needs a real completeness signal from the walker plus a catalog revision the palette can subscribe to, re-running the active query (debounced) when coverage changes, without disturbing keyboard selection or the input.
