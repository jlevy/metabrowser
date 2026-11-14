---
type: is
id: is-01m7d6qymfet9180bcn40m0bjb
title: Find what lengthened the held-key skim's last row at final main (H91 (c) rejected in exp-079)
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-14T14:17:52.014Z
updated_at: 2026-11-14T14:17:52.014Z
---
In exp-079, H91 (c)'s deciding metric held (file envelopes per skim 6 to 2), but its guard ready_after_last_input_ms went 46.2 (42.9-50.3) to 65.0 (56.8-72.5) ms, ranges apart, 3 of 6 pairs beyond 1.3x, which exp-085's declared rule rejects. The excess matches, within a frame, a longer select-to-ready span of the final row, so the time is likely the last row's own render, slower at final main, not the coalescing. Find which change since exp-085's candidate lengthened it (bisect the skim across the lanes merged after it), then re-judge H91 (c) on main, or revert it if the coalescing is the cause. The code is on main now.
