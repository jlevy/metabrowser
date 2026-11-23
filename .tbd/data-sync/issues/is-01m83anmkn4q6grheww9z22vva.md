---
type: is
id: is-01m83anmkn4q6grheww9z22vva
title: Fix pre-row Files navigation chrome layout shift in main CI
kind: bug
status: in_progress
priority: 1
version: 3
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45111133543
    at: 2026-11-23T04:31:12.047Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hhr2r1bmm0ve8a6qs5nnqw
hold: null
hold_until: null
created_at: 2026-11-23T04:29:48.013Z
updated_at: 2026-11-23T04:31:12.052Z
started_at: 2026-11-23T04:31:07.504Z
---
Main CI run 45111133543 at b131131a3 shows pre-row shifts at 201/207 ms in the navigation filter bar, tab and root details. Chrome 3.12 dark 300 px CLS 0.00015 and 3.14 dark 180 px CLS 0.00011. Prior known folder age and empty-tree wrap cases have different sources. Measure the source rectangles and startup ordering, then fix the cause without relaxing layout thresholds.
