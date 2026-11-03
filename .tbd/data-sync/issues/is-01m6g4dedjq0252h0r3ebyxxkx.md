---
type: is
id: is-01m6g4dedjq0252h0r3ebyxxkx
title: "PR #285 Qodo r4451789336: a failed /pulls landing read settles on 'Select a pull request.'"
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
hold: null
hold_until: null
created_at: 2026-11-03T07:19:12.050Z
updated_at: 2026-11-03T11:44:17.897Z
started_at: 2026-11-03T07:38:39.074Z
---
https://github.com/jlevy/metabrowser/pull/285#discussion_r4451789336 (Qodo, on 353296de). followLanding (builtin_plugins/github/pulls-panel.js) turns a rejected request or a non-envelope answer into a null envelope; describeLanding(null) says 'Select a pull request.' and landingWaits(null) is false, so the landing stops reading and a later good read never updates it. Valid, Low: the single read before round 2 said the same and never retried; the tab's own notice shows the error. Fix sketch: treat a null envelope as not settled while visible, read again at SLOW_POLL_MS, leave a pin_changed 409 silent as the list does; session step: a thrown request (scripted rejection) then landing_gh_missing. Not done: the work paused for a handoff at 353296de.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Follow-up Review D at 54d7c9f7 independently verifies failed/rejected/non-envelope landing reads remain visibly unavailable and retry at the slow visible-page interval, while pin_changed stays silent. Retained at owning #285 9d9c4049 and final integration. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
