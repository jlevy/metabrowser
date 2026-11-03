---
type: is
id: is-01m6gft6cfr7b50arr0rpdk1by
title: "PR #288 D2: keep repair pending across pre-job polling responses"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T10:38:24.142Z
updated_at: 2026-11-03T20:17:09.736Z
closed_at: 2026-11-03T20:17:09.736Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Independent Review D at006bb1b5: GET sent after POST can reach server first and win shownRequest with pre-job envelope; later202 refreshing envelope is ignored, refreshPending clears, and Files remounts before recovery completes, consuming its completion remount. Root owns POST/poll response-order barrier preserving latest-wins metadata and one post-job remount. Production probe durable in metabrowser-review-evidence-01a1a051.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Review D2 is fixed in 64afc0d9 and independently rechecked, retained at final #288 58270d69. No new GET begins while the explicit POST is unacknowledged; an older in-flight GET retains latest-wins ordering. Independent race probes show one mount at acknowledgement and exactly two at actual completion. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
