---
type: is
id: is-01m6hpa99cxdtgg3w4zk75qe25
title: Repaint the PR row window when its viewport height changes
kind: bug
status: closed
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:51:17.291Z
updated_at: 2026-11-04T17:14:29.427Z
started_at: 2026-11-03T21:52:23.917Z
closed_at: 2026-11-04T17:14:29.426Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent mounted-DOM probe enlarged the scroll viewport from100px to3000px and delivered all applicable ResizeObserver events, but the virtualized list retained43 rows and visible spacer area until another scroll or poll. Observe the actual scroll viewport as well as row/list sizes, queue a window frame on resize, and disconnect on disposal. Recheck unchanged viewport-resize probe and actual browser resize/expanded-row height behavior.

## Notes

Fixed using existing list ResizeObserver to also observe scrollRoot and queue a window frame; disposal disconnects it. Unchanged independent viewport probe red43rows after100to3000px resize, then green113rows/no visible spacer. Permanent mounted-DOM test also covers distant focus protection, absolute ARIA and cleanup. Final29 affected tests/both browser type configs/9 scoped UI goldens pass. Exact hashes and raw evidence in catalog-ui-m13a/writer-report.json. Root owns final commit/full gate/closure.
