---
type: is
id: is-01m6hpa99cxdtgg3w4zk75qe25
title: Repaint the PR row window when its viewport height changes
kind: bug
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:51:17.291Z
updated_at: 2026-11-03T22:03:02.513Z
started_at: 2026-11-03T21:52:23.917Z
---
Independent mounted-DOM probe enlarged the scroll viewport from100px to3000px and delivered all applicable ResizeObserver events, but the virtualized list retained43 rows and visible spacer area until another scroll or poll. Observe the actual scroll viewport as well as row/list sizes, queue a window frame on resize, and disconnect on disposal. Recheck unchanged viewport-resize probe and actual browser resize/expanded-row height behavior.

## Notes

Fixed using existing list ResizeObserver to also observe scrollRoot and queue a window frame; disposal disconnects it. Unchanged independent viewport probe red43rows after100to3000px resize, then green113rows/no visible spacer. Permanent mounted-DOM test also covers distant focus protection, absolute ARIA and cleanup. Final29 affected tests/both browser type configs/9 scoped UI goldens pass. Exact hashes and raw evidence in catalog-ui-m13a/writer-report.json. Root owns final commit/full gate/closure.
