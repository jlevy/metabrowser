---
type: is
id: is-01m774r6nmb6sxnp5gbpy1sfaz
title: Prose font preload, static tree reveals, held-key coalescing, palette group order
kind: task
status: closed
priority: 2
version: 8
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
updated_at: 2026-11-13T22:19:14.652Z
started_at: 2026-11-12T05:55:54.209Z
closed_at: 2026-11-13T22:19:14.651Z
close_reason: "Landed in #370 (merge f4817752). exp-064 (H91): (a) fonts, cold Markdown shift 0.0033 to 0; (b) deep landing shift 0.057 to 0; (d) palette row replacements 11 to 0, all accepted. (c) the held key, unresolved in exp-064, accepted in exp-085: file envelopes 6 to 2 every run, its guard's two pairs beyond 1.3x explained by the pre-registered evidence (6 of 7 paced pairs judged). Accounted cost: idle face loading fetches unused KPress faces once."
resolution: null
duplicate_of: null
---
Preload PT Serif faces when prose uses them; do not animate programmatic tree reveals; coalesce held arrow keys in the Files tree; fixed position for PR results in the palette. Measured as shift without input and requests per skim.

## Notes

PR #370. Deep landing fixed (936fbee7: server inlines the landing path's folders open; first tree paint selects and shows the row; nothing fetched or scrolled after). In-session reveals open instantly and scroll the new selection into view in one frame (078c4c69). Official exp-064 on the fixed harness.
