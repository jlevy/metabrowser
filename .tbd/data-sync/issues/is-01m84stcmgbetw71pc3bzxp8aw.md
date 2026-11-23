---
type: is
id: is-01m84stcmgbetw71pc3bzxp8aw
title: "Rendered diff: show a file with a task list, its boxes' ticks as changes"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-11-23T18:13:46.765Z
updated_at: 2026-11-23T18:13:46.765Z
---
markdown_projection.py refuses any file with a task list (task_list), because KPress writes the checkbox as raw HTML and the inert render drops its checked state. Project the checkbox as an inert element that keeps its state, and count the state in the block's signature so ticking a box is a change.
