---
type: is
id: is-01m774r7k4mqvs813sjppzvceh
title: "PR page: join the click to the peek, same-frame list collapse, hold Changes first paint"
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:37.443Z
updated_at: 2026-11-12T06:11:46.652Z
started_at: 2026-11-12T06:11:46.651Z
---
One read of the selected PR per click (join the mousedown peek); collapse the old and expand the new Pulls row in one frame; reserve a selected row's file-tree height at the click or open it only when rows are known; hold Changes first paint for rendered diffs already in flight or reserve their heights. Measured as selected-record reads per click and no-input shift (largest today 0.146 from the late file tree).
