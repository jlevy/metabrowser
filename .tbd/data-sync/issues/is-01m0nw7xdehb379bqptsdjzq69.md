---
type: is
id: is-01m0nw7xdehb379bqptsdjzq69
title: Re-arm the viewport sweep on resize (H38/S5)
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:37.837Z
updated_at: 2026-08-22T23:17:37.837Z
---
Review suggestion S5. Scroll and expand cover the two ways a reader ACTS a row into view. A window resize or pane-splitter drag also reveals rows and re-arms nothing, so a reader who enlarges the window leaves newly revealed folders cold until they scroll. A resize listener or ResizeObserver beside the existing scroll handler closes it.
