---
type: is
id: is-01m774r3cs24qrntm810jeqndz
title: "Git: comparison cache by commit ID; route memo by refs fingerprint"
kind: task
status: in_progress
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:33.134Z
updated_at: 2026-11-12T15:26:03.374Z
started_at: 2026-11-12T05:53:04.459Z
---
Browser cache of diff comparisons keyed by full commit ID; server memo of git refs, log pages, and summary keyed by a refs fingerprint. Measured as commit revisit requests and painted-ready, and route server time.

## Notes

PR #368. Round-1 reviews at 60a4e623 (A 5876259351, B 5876259603, C 5876259835): 0 Blocker, 1 High, 6 Medium, 13 Low. Addressed at 4b0e1233 (d85ee2d3, 7fd879c6, 4b0e1233). Dispositions 6827183008/6827196003/6827213204; deferrals mb-ak8u, mb-32en, mb-bjt4 (note 6827258806). Follow-up review D (round 2, 4b0e1233, 5877077982): approve; 2 Low (D1 linked-worktree input tests and packed-refs; D2 memo doc), queued as a tests-and-docs commit after the rounds, plus a check that reftable skips pass CI's admitted-git 2.43.7 job. Official exp-061 and exp-063 on harness v4 at 4b0e1233 queued after the layout series.
