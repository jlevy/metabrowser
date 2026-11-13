---
type: is
id: is-01m7b2jkpa89v1kw7dbm0vvfys
title: Background GitHub core preparation slows concurrent interactive git requests by about 50 ms
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-13T18:26:33.801Z
updated_at: 2026-11-13T18:26:33.801Z
---
Found by the #368 diagnostic traces (exp-081/082 follow-up, 2026-11-13). With a pull-cores-prepare from the Pulls catalog walk overlapping or answering 50-127 ms before them, /api/plugin/diff/comparison server time rose from 77.6-84.4 ms to 128.3-155.7 ms and the commit detail from 22.4-28.0 ms to 71.7-82.7 ms (Server-Timing srv). That moved commits.hover_click's ready from about 16 ms to 35 ms (one frame) and put commits.cold.1 in its slow mode. Suspected: work the prepare leaves running after it answers (cached_batch in asyncio.to_thread, and whatever follows). A corrected contention sweep (fresh pages through next_after, comparison and commit at 0/100/300 ms after a prepare answers) is written but not yet run. Fix direction: interactive requests first, background preparation yields or is throttled while a reader is navigating.
