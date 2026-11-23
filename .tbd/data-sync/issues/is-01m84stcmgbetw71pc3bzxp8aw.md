---
type: is
id: is-01m84stcmgbetw71pc3bzxp8aw
title: "Rendered diff: show a file with a task list, its boxes' ticks as changes"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/kpress/pull/82
    at: 2026-11-23T22:02:38.657Z
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: blocked
hold_until: null
created_at: 2026-11-23T18:13:46.765Z
updated_at: 2026-11-23T22:02:48.360Z
started_at: 2026-11-23T18:26:01.829Z
---
markdown_projection.py refuses any file with a task list (task_list), because KPress writes the checkbox as raw HTML and the inert render drops its checked state. Project the checkbox as an inert element that keeps its state, and count the state in the block's signature so ticking a box is a change.

## Notes

Blocked on KPress: native task-list tokens are in jlevy/kpress PR #82 (kpr-1m2b, CI green), and its release is tracked as kpr-nehd (0.3.10). Once released, bump kpress here and remove the task-list refusal in markdown_projection.py; the box's state is token.meta["checked"].
