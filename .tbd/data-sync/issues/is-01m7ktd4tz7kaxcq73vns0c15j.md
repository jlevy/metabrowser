---
type: is
id: is-01m7ktd4tz7kaxcq73vns0c15j
title: "PR #494 review A3: scrollspy session asserts its own viewport stub, not KPress's viewport.js"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7ksbsx0kcg5rk05fy23nxc5
hold: null
hold_until: null
created_at: 2026-11-17T03:56:56.030Z
updated_at: 2026-11-17T04:19:33.012Z
started_at: 2026-11-17T03:57:11.320Z
closed_at: 2026-11-17T04:19:33.012Z
close_reason: "Fixed in 58b6b1c1 on #494: the scrollspy session loads the installed viewport.js with the pane marked [data-kpress-viewport]; the passive flag, a pane-resize step, and resize-observer disposal now come from KPress; golden regenerated."
resolution: null
duplicate_of: null
---
Review A finding A3, Low. tests/dom/markdown-toc-scrollspy-session.js:409 reads passiveScrollListener from the session's own viewportContext.onScroll stub; viewportBounds and addViewportResizeListener are stubs too (lines 37-44), so the disposal counts cover the stub's resize listener, not KPress's ResizeObserver path. Load the installed viewport.js with the shim pane marked [data-kpress-viewport], or relabel the assertion.
