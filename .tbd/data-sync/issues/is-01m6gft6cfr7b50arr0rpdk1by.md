---
type: is
id: is-01m6gft6cfr7b50arr0rpdk1by
title: "PR #288 D2: keep repair pending across pre-job polling responses"
kind: bug
status: open
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T10:38:24.142Z
updated_at: 2026-11-03T11:44:12.522Z
---
Independent Review D at006bb1b5: GET sent after POST can reach server first and win shownRequest with pre-job envelope; later202 refreshing envelope is ignored, refreshPending clears, and Files remounts before recovery completes, consuming its completion remount. Root owns POST/poll response-order barrier preserving latest-wins metadata and one post-job remount. Production probe durable in metabrowser-review-evidence-01a1a051.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Review D2 is fixed in 64afc0d9 and independently rechecked, retained at final #288 58270d69. No new GET begins while the explicit POST is unacknowledged; an older in-flight GET retains latest-wins ordering. Independent race probes show one mount at acknowledgement and exactly two at actual completion. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
