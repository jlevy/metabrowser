---
type: is
id: is-01m774r3cs24qrntm810jeqndz
title: "Git: comparison cache by commit ID; route memo by refs fingerprint"
kind: task
status: in_progress
priority: 1
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
created_at: 2026-11-12T05:47:33.134Z
updated_at: 2026-11-12T17:07:23.119Z
started_at: 2026-11-12T05:53:04.459Z
---
Browser cache of diff comparisons keyed by full commit ID; server memo of git refs, log pages, and summary keyed by a refs fingerprint. Measured as commit revisit requests and painted-ready, and route server time.

## Notes

PR #368 at a4b6aba9 (official records 3a3238bb, review D fixes a4b6aba9; dispositions D 6830344513). Official exp-061 (6 interleaved pairs, harness v4, 0 refused): H88(a) commit revisit 1 request to 0, painted ready 146.8 to 31.0 ms and 188.9 to 29.6 ms (pairs 0.21x, 0.16x, 6 of 6 beyond) BUT guard failed: commits.hover_click 30.8 to 47.8 ms (pairs 1.55x, 5 of 6 higher, frames to ready 1 to 2) -> unresolved. H88(b) route memo: log 182 to 6.8 ms (26x), summary 184 to 3.4 ms (52x), refs 28.4 to 3.6 ms (7.5x) with ranges overlapping -> unresolved. B8 correctness guard: 45 of 45 equal after ref moves. Next: diagnose hover_click and refs overlap; confirmation round exp-081.
