---
type: is
id: is-01m6hpa99cxdtgg3w4zk75qe25
title: Repaint the PR row window when its viewport height changes
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:51:17.291Z
updated_at: 2026-11-03T21:52:23.918Z
started_at: 2026-11-03T21:52:23.917Z
---
Independent mounted-DOM probe enlarged the scroll viewport from100px to3000px and delivered all applicable ResizeObserver events, but the virtualized list retained43 rows and visible spacer area until another scroll or poll. Observe the actual scroll viewport as well as row/list sizes, queue a window frame on resize, and disconnect on disposal. Recheck unchanged viewport-resize probe and actual browser resize/expanded-row height behavior.
