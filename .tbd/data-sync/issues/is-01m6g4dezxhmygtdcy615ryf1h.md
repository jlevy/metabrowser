---
type: is
id: is-01m6g4dezxhmygtdcy615ryf1h
title: "PR #285 Qodo r4451789342: an empty cached list's landing stops reading while its refresh runs"
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
hold: null
hold_until: null
created_at: 2026-11-03T07:19:12.636Z
updated_at: 2026-11-03T20:17:09.803Z
started_at: 2026-11-03T07:38:39.086Z
closed_at: 2026-11-03T20:17:09.803Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
https://github.com/jlevy/metabrowser/pull/285#discussion_r4451789342 (Qodo, on 353296de). landingWaits (builtin_plugins/github/pulls-panel.js) requires !complete and state absent or pending, so a complete empty list (fetched 0) that is stale and refreshing settles on 'No pull requests.' and stays there if the refresh finds rows. Valid, Low. Fix sketch: an envelope with fetched 0 and refreshing true waits whatever its state or complete; the recorder needs an empty complete list, its refresh, and the refreshed list for a session step. Not done: the work paused for a handoff at 353296de.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Follow-up Review D at 54d7c9f7 independently verifies a complete empty list keeps polling while refresh is active, then reflects resulting rows. Production recordings cover all three states. Retained at owning #285 9d9c4049. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
