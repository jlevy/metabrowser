---
type: is
id: is-01m6g4dedjq0252h0r3ebyxxkx
title: "PR #285 Qodo r4451789336: a failed /pulls landing read settles on 'Select a pull request.'"
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
created_at: 2026-11-03T07:19:12.050Z
updated_at: 2026-11-03T20:17:09.796Z
started_at: 2026-11-03T07:38:39.074Z
closed_at: 2026-11-03T20:17:09.796Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
https://github.com/jlevy/metabrowser/pull/285#discussion_r4451789336 (Qodo, on 353296de). followLanding (builtin_plugins/github/pulls-panel.js) turns a rejected request or a non-envelope answer into a null envelope; describeLanding(null) says 'Select a pull request.' and landingWaits(null) is false, so the landing stops reading and a later good read never updates it. Valid, Low: the single read before round 2 said the same and never retried; the tab's own notice shows the error. Fix sketch: treat a null envelope as not settled while visible, read again at SLOW_POLL_MS, leave a pin_changed 409 silent as the list does; session step: a thrown request (scripted rejection) then landing_gh_missing. Not done: the work paused for a handoff at 353296de.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Follow-up Review D at 54d7c9f7 independently verifies failed/rejected/non-envelope landing reads remain visibly unavailable and retry at the slow visible-page interval, while pin_changed stays silent. Retained at owning #285 9d9c4049 and final integration. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
