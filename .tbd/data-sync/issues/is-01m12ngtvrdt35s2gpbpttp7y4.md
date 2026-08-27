---
type: is
id: is-01m12ngtvrdt35s2gpbpttp7y4
title: State the git-history-window scroll-origin contract in its module docstring
kind: chore
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-27T22:30:17.720Z
updated_at: 2026-08-27T23:15:06.357Z
closed_at: 2026-08-27T23:15:06.356Z
close_reason: "Fixed in 0715a66: git-history-window.js module header now states the coordinate contract — every scrollTop it accepts and returns is relative to the first history row, the caller owns the conversion, and passing a raw scroller offset fails quietly because overscan hides it."
resolution: null
duplicate_of: null
---
git-history-window.js reads as a pure module — read(scrollTop, viewportHeight) in, logical row range out — which implies the caller may supply any coordinate space. It may not: the arithmetic assumes the rows begin at offset 0 of the scroller whose scrollTop is passed in. One sentence in the module docstring would have prevented mb-180g and will prevent the next one. Pairs with mb-180g; do them together.
