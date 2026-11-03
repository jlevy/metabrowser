---
type: is
id: is-01m6hp53m3z5s1a4y147rcdrk2
title: Preserve newer refresh state while catalog windows are staged
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:48:27.650Z
updated_at: 2026-11-03T22:03:02.234Z
started_at: 2026-11-03T21:48:59.067Z
---
Independent production-controller probe reproduced an older GET awaiting several generation-consistent catalog windows. A later explicit Retry POST202 adopts a newer refreshing envelope, but the GET continuation lowers shownRequest and overwrites it with an older non-refreshing envelope. Recheck response ownership after every staged await or commit coherent rows without rolling back newer refresh state; retain the unchanged independent controller-races probe and test both completion orders.

## Notes

Fixed in shared catalog UI; source pulls-panel.js SHA256 9f940e6d33c9fdc36f02e58bd92da6f6a2fea8a4665fd11e59fd266ed532a764. Unchanged independent controller-races probe red then green; reviewer rechecked clean. Permanent delayed-order test protects rows/version, latest envelope/timer, later coherent completion, and stale error/more state. Final29 affected tests, both browser type configs,9 scoped UI goldens pass. Durable writer-report.json and raw red/green logs under agent-evidence/metabrowser-pr-stack-01a1a051/catalog-ui-m13a. Root owns final commit/full gate/closure.
