---
type: is
id: is-01m6j331jhmbnr4wdhjpf03pvs
title: Replay the active diff selection on repeated same-page route notices
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: pulls_navigation
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-04T01:34:31.503Z
updated_at: 2026-11-04T01:43:22.675Z
started_at: 2026-11-04T01:37:39.123Z
---
Independent real mounted file-row probe at7cabc shows same-page setCurrent(number,null) clears1→0 selected file because followCurrentFile skips unchanged handle. Replay/preserve an owned current observation at route boundary, guard stale page/PR callbacks, retain explicit non-null file precedence and null/unavailable jump behavior. Cohesive fix with mb-l5il; real pagehost/history and delayed subscription controls, external whole-shell reproduction, independent recheck and fresh artifact gates required.

## Notes

Independent original mounted-page probe pinned7cab fixture reproduced before1/after0 on repeated samepage setCurrent(number,null). Fixed by replaying existing immediate observation only at null-file route boundary; no replay for explicit file. CapturedPR/page/subscriptionepoch/disposed guards reject delayed, ignored-unsubscribe and same-handle stale callbacks. Regression covers explicitfile throughnull/unavailable report, new delayedpage, Back and disposal. Independent unchanged-assertion probe now1→1 plus6lifecycle controls clean; panelSHA256511ea82aa7596f607867d4a9627fdacf512dc1c924878d29cf1f896605ed599a. Final selection-fix-handoff.json records7frozenfiles and72focusedtests/types/goldens/lint/parity85pass. Coordinator owns forwardcommit/finalartifactchecks; leave open until final readiness.
