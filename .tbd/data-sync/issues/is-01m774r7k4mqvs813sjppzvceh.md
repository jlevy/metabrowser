---
type: is
id: is-01m774r7k4mqvs813sjppzvceh
title: "PR page: join the click to the peek, same-frame list collapse, hold Changes first paint"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:37.443Z
updated_at: 2026-11-12T05:48:12.724Z
---
One read of the selected PR per click; collapse the old and expand the new list row in one frame; hold Changes first paint for rendered diffs already in flight or reserve their heights. Measured as duplicate reads and shift.
