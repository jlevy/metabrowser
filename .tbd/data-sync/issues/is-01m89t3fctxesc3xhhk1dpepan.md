---
type: is
id: is-01m89t3fctxesc3xhhk1dpepan
title: Stack page reflows and flickers while it renders (first paint differs from the JS render)
kind: bug
status: closed
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/845
    at: 2026-11-25T18:10:04.650Z
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T16:54:56.664Z
updated_at: 2026-11-25T22:25:43.912Z
started_at: 2026-11-25T16:56:18.156Z
closed_at: 2026-11-25T22:25:43.910Z
close_reason: "Merged in stack #846 (main 1cfd383d3)"
resolution: null
duplicate_of: null
---
User report: 'when I click on the whole stack page and it's rendering, it's reflowing and flickering, like it's rendering it one way, then changing the way it's rendering the docs page or the changes page in JavaScript.' Find the mechanism: the server's or the first paint's layout differs from what the JS renderer draws afterwards (or a late stylesheet/script, or content arriving in stages without reserved room). Fix so the first paint is the final layout (nothing moves from first paint to settled), as the Files panel's totals check enforces, and pin it with a layout-shift Chrome check plus a browserless golden of the first-paint vs settled structure. Check whether the PR page's docs and changes views have the same problem.
