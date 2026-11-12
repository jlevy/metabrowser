---
type: is
id: is-01m774r3cs24qrntm810jeqndz
title: "Git: comparison cache by commit ID; route memo by refs fingerprint"
kind: task
status: in_progress
priority: 1
version: 9
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
updated_at: 2026-11-12T17:37:51.707Z
started_at: 2026-11-12T05:53:04.459Z
---
Browser cache of diff comparisons keyed by full commit ID; server memo of git refs, log pages, and summary keyed by a refs fingerprint. Measured as commit revisit requests and painted-ready, and route server time.

## Notes

PR #368 at bc3f0459. Official exp-061 (6 pairs, harness v4): H88(a) revisit 1 request to 0, painted ready 146.8 to 31.0 and 188.9 to 29.6 ms (6 of 6 pairs beyond); guard flag commits.hover_click 30.8 to 47.8 ms diagnosed as a race between the 300 ms hover debounce and a background catalog walk whose phase the faster revisits shift (code adds no work on the path; route timings equal) -> unresolved. H88(b) log 26x, summary 52x, refs 7.5x with overlap from the 5 s identity refresh every fourth pair on both builds -> unresolved. B8 correctness 45/45. Explanations recorded in bc3f0459. Next: fix render-cache store sweep (O(n) per insert), mechanism probe (comparison with a concurrent catalog page), confirmation exp-081 under the runbook's standard rule declared before the series, with load exclusion.
