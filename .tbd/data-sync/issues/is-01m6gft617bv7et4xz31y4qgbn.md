---
type: is
id: is-01m6gft617bv7et4xz31y4qgbn
title: "PR #288 D1: render Files immediately after leaving a pending repair"
kind: bug
status: open
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T10:38:23.782Z
updated_at: 2026-11-03T11:44:11.960Z
---
Independent Review D at006bb1b5: start explicit Files Refresh, enter Conversation while POST waits, complete job, return via history to Files. paintFiles clears filesRefresh and returns when diffFor was disposed, leaving Conversation body under Files and stale readiness. Root owns route/render ownership fix with production-controller regressions for pending/completed/failed jobs and explicit newer selection.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Review D1 is fixed in 64afc0d9 and independently rechecked, retained at final #288 58270d69. Returning from Conversation immediately renders Files for pending, completed, or failed explicit repair, with correct replacement readiness and old-selection ownership. Production history/lifecycle regressions and actual Chrome variants pass. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
