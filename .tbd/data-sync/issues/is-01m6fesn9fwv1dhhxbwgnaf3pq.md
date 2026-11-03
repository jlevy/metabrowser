---
type: is
id: is-01m6fesn9fwv1dhhxbwgnaf3pq
title: "PR #283 C5: empty-boundary returns of merge_base_answer trust a read taken before Git ran"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T01:01:23.630Z
updated_at: 2026-11-03T01:54:04.636Z
started_at: 2026-11-03T01:33:07.515Z
closed_at: 2026-11-03T01:54:04.635Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: C5 boundary re-read on every return"
resolution: null
duplicate_of: null
---
Medium. Review C. git/shallow.py:100-113. Same as Qodo inline comment 2 https://github.com/jlevy/metabrowser/pull/283#discussion_r4449381232
