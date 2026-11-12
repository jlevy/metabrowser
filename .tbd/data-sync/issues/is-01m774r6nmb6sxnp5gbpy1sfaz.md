---
type: is
id: is-01m774r6nmb6sxnp5gbpy1sfaz
title: Prose font preload, static tree reveals, held-key coalescing, palette group order
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
created_at: 2026-11-12T05:47:36.498Z
updated_at: 2026-11-12T07:24:36.030Z
started_at: 2026-11-12T05:55:54.209Z
---
Preload PT Serif faces when prose uses them; do not animate programmatic tree reveals; coalesce held arrow keys in the Files tree; fixed position for PR results in the palette. Measured as shift without input and requests per skim.

## Notes

Implemented on claude/perf-layout (d797b7b4). Font wait capped at 100 ms instead of preload; programmatic reveals instant; held-key walk with WALK_SETTLE_MS 120 (harness must send autoRepeat keyDowns); palette groups by kind. Awaiting exp-064.
