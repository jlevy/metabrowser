---
type: is
id: is-01m0k5xf3ej2n2b7f3zawg9r1p
title: Window rendered nav rows so the count follows the viewport
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:57.966Z
updated_at: 2026-08-21T22:48:50.810Z
---
At 1M files the nav renders 25,122 rows and 276,789 DOM nodes at once, with no windowing. docs/large-content-rendering.md already establishes that element count and memory are the real ceiling and measures the strategy ladder for document content; this is a different surface and needs its own measurement of the same trade.

The specific thing to measure before choosing: what windowing costs find-in-page and select-all across the whole tree. That document's own table puts a virtualized window at 33 ms first paint against 633 ms for pre-broken lines, and marks native find, selection, and print as lost. Record the trade rather than assuming it.
