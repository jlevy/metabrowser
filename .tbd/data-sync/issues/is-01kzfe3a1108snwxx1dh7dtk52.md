---
type: is
id: is-01kzfe3a1108snwxx1dh7dtk52
title: "Quick File: an open search does not re-run when the catalog grows"
kind: bug
status: open
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-08T00:59:18.432Z
updated_at: 2026-08-09T17:43:16.828Z
---
Half of this landed in 16678d3; re-scoped to what remains.

DONE: known_file_catalog.snapshot() no longer hardcodes complete: false. It reports catalogComplete, set once a complete bulk feed is applied or the walk finishes after an incomplete one, so the status line can tell indexing from complete.

REMAINING: search_palette.js still subscribes only to the search controller (const unsubscribe = options.controller.subscribe(consumeState)), and the controller publishes only in response to a keystroke. A query typed while the bulk feed is still arriving keeps its original result set after coverage completes; the user has to edit the query to see the rest.

Needs a catalog revision the palette can watch, re-running the active query debounced when coverage changes, without disturbing keyboard selection, the input value, or scroll position. Lower urgency than when filed: the bulk fetch is one request and usually completes before a query is typed. It still bites on a large root, which is exactly where search matters most.
