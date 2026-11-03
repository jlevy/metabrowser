---
type: is
id: is-01m6gft617bv7et4xz31y4qgbn
title: "PR #288 D1: render Files immediately after leaving a pending repair"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T10:38:23.782Z
updated_at: 2026-11-03T20:17:09.729Z
closed_at: 2026-11-03T20:17:09.729Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Independent Review D at006bb1b5: start explicit Files Refresh, enter Conversation while POST waits, complete job, return via history to Files. paintFiles clears filesRefresh and returns when diffFor was disposed, leaving Conversation body under Files and stale readiness. Root owns route/render ownership fix with production-controller regressions for pending/completed/failed jobs and explicit newer selection.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Review D1 is fixed in 64afc0d9 and independently rechecked, retained at final #288 58270d69. Returning from Conversation immediately renders Files for pending, completed, or failed explicit repair, with correct replacement readiness and old-selection ownership. Production history/lifecycle regressions and actual Chrome variants pass. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
