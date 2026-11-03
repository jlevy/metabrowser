---
type: is
id: is-01m6g4dezxhmygtdcy615ryf1h
title: "PR #285 Qodo r4451789342: an empty cached list's landing stops reading while its refresh runs"
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
created_at: 2026-11-03T07:19:12.636Z
updated_at: 2026-11-03T11:44:18.445Z
started_at: 2026-11-03T07:38:39.086Z
---
https://github.com/jlevy/metabrowser/pull/285#discussion_r4451789342 (Qodo, on 353296de). landingWaits (builtin_plugins/github/pulls-panel.js) requires !complete and state absent or pending, so a complete empty list (fetched 0) that is stale and refreshing settles on 'No pull requests.' and stays there if the refresh finds rows. Valid, Low. Fix sketch: an envelope with fetched 0 and refreshing true waits whatever its state or complete; the recorder needs an empty complete list, its refresh, and the refreshed list for a session step. Not done: the work paused for a handoff at 353296de.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Follow-up Review D at 54d7c9f7 independently verifies a complete empty list keeps polling while refresh is active, then reflects resulting rows. Production recordings cover all three states. Retained at owning #285 9d9c4049. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
