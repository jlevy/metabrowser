---
type: is
id: is-01kzfe3a1108snwxx1dh7dtk52
title: "Quick File: an open search does not re-run when the catalog grows"
kind: bug
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
created_at: 2026-08-08T00:59:18.432Z
updated_at: 2026-08-10T01:52:47.763Z
---
Half of this landed in 16678d3; re-scoped to what remains.

DONE: known_file_catalog.snapshot() no longer hardcodes complete: false. It reports catalogComplete, set once a complete bulk feed is applied or the walk finishes after an incomplete one, so the status line can tell indexing from complete.

REMAINING: search_palette.js still subscribes only to the search controller (const unsubscribe = options.controller.subscribe(consumeState)), and the controller publishes only in response to a keystroke. A query typed while the bulk feed is still arriving keeps its original result set after coverage completes; the user has to edit the query to see the rest.

Needs a catalog revision the palette can watch, re-running the active query debounced when coverage changes, without disturbing keyboard selection, the input value, or scroll position. Lower urgency than when filed: the bulk fetch is one request and usually completes before a query is typed. It still bites on a large root, which is exactly where search matters most.

## Notes

Design review 2026-08-09: LOW RISK, ~half day with tests.

Shape: give the catalog a subscribe() mirroring the fileStore subscriber array that already exists in app.js (fileStoreSubscribers / notifyFileStoreSubscribers) — same pattern, same codebase idiom. The palette subscribes; on revision change with the overlay open, a non-empty query, and a received searchState, re-run the active query debounced (~100ms).

Why it is safe: every dangerous part already exists and is tested. controller.search cancels superseded work; consumeState preserves selection by result id; the held-rows path means a re-run of the SAME query repaints without flicker; renderedQuery === input.value stays true throughout, so rows never go inert. Searches do not mutate the catalog, so no feedback loop; observeNavigation bumps revision on open, guarded by the overlay-hidden check plus debounce. Free rider: refresh the idle 'N observed files' status line on the same signal.

Traps: debounce-timer cleanup on close/dispose (same pattern as searchingStatusTimer).
