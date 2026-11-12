---
type: is
id: is-01m774r6nmb6sxnp5gbpy1sfaz
title: Prose font preload, static tree reveals, held-key coalescing, palette group order
kind: task
status: in_progress
priority: 2
version: 6
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
updated_at: 2026-11-12T10:32:15.869Z
started_at: 2026-11-12T05:55:54.209Z
---
Preload PT Serif faces when prose uses them; do not animate programmatic tree reveals; coalesce held arrow keys in the Files tree; fixed position for PR results in the palette. Measured as shift without input and requests per skim.

## Notes

PR #370. Pilot: fonts shift 0.0033 to 0 (painted-ready 265 to 320 ms, overlapping, check on fixed harness); palette replacements 11 to 0; skim requests 6 to 1. Deep reveal prediction failed: no-input shift 0.05 to 0.12 as the unanimated reveal jumps 2,800 px after first paint; fix in progress (landing tree inlined with the ancestry expanded at first paint). Official exp-064 on the fixed harness.
