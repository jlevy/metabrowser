---
type: is
id: is-01m6f2my0bz2mvdrn5d0j9wqhj
title: "PR #273 https://github.com/jlevy/metabrowser/pull/273#discussion_r4436440679: a review range starting on the other side loses its start"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m6f2mj3gymr1nybga3v8b9xw
created_at: 2026-11-02T21:29:05.802Z
updated_at: 2026-11-02T22:33:30.554Z
---
Qodo inline comment on pull-page.js:407-411.

## Notes

Deferred from PR 273. Waits on a change to the record's schema (PULL_RECORD_SCHEMA, pull_record.py), which belongs with mb-a0cq's subject_type. Keep start_side from GitHub (pulls.py) and use it in hunkView's back-count and commentedSpan. Sample of 2026-11-02: 6,533 review comments across 14 repositories, 35 with start_side other than side, 17 with both line numbers; the first line is in the tail for 9, behind the disclosure for 4, not locatable for 4. Disposition: https://github.com/jlevy/metabrowser/pull/273#discussion_r4448591207
