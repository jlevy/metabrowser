---
type: is
id: is-01m83bbgeajzxhr6xkpabzgs0c
title: Restore CLI 0.13.0 first directory row below the browser release budget
kind: bug
status: in_progress
priority: 1
version: 3
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45112075401
    at: 2026-11-23T04:41:51.934Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hhr36mmrjwfw662gmgngf6
hold: null
hold_until: null
created_at: 2026-11-23T04:41:44.647Z
updated_at: 2026-11-23T04:41:51.962Z
started_at: 2026-11-23T04:41:48.946Z
---
Five admitted foreground Chrome comparisons put the v0.13.0 candidate at 697–765 ms from navigation to the first directory row, versus 131–242 ms in v0.12.0 and the required 350 ms. The backend first-row median and ordered results match. Attribute the browser-side delay, fix a focused cause with the new startup font work accounted for, then rerun the exact candidate.
