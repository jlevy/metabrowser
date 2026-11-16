---
type: is
id: is-01m7jqbrrhakj66ck33zz20t24
title: "PR #478 A1: a comparison first read by Changes is never kept"
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
created_at: 2026-11-16T17:44:30.736Z
updated_at: 2026-11-16T18:19:26.024Z
started_at: 2026-11-16T17:44:41.908Z
closed_at: 2026-11-16T18:19:26.023Z
close_reason: "Fixed in 9f22279b9 on PR #478 (head d9782d01e): take() reads through the keep; prefetch session and headerSummary Changes-first steps"
resolution: null
duplicate_of: null
---
Review A (round 1) of PR #478, https://github.com/jlevy/metabrowser/pull/478#pullrequestreview-5924265457. Severity: Medium. Where: comparison-prefetch.js:455-468 (take), pull-page.js:5556, diff/index.js:372-375
