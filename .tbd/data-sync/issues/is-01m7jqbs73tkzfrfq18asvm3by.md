---
type: is
id: is-01m7jqbs73tkzfrfq18asvm3by
title: "PR #478 A2: the warmer repeats outcomes that leave nothing in the keep; record reads outside WARM_PER_HOUR"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7jkakkfddytvc7cwa16v0dj
hold: null
hold_until: null
created_at: 2026-11-16T17:44:31.202Z
updated_at: 2026-11-16T18:19:26.377Z
started_at: 2026-11-16T17:44:42.359Z
closed_at: 2026-11-16T18:19:26.376Z
close_reason: "Fixed in 9f22279b9 on PR #478 (head d9782d01e): every outcome settles for fresh_for_s; cap before the record read; not kept noted; ten-ask session step"
resolution: null
duplicate_of: null
---
Review A (round 1) of PR #478, https://github.com/jlevy/metabrowser/pull/478#pullrequestreview-5924265457. Severity: Medium. Where: comparison-prefetch.js:573-627, :494-495
