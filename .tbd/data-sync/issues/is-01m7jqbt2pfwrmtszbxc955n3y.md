---
type: is
id: is-01m7jqbt2pfwrmtszbxc955n3y
title: "PR #478 A4: a take() while the page waits for idle joins the shared request with no signal"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7jkakkfddytvc7cwa16v0dj
hold: null
hold_until: null
created_at: 2026-11-16T17:44:32.085Z
updated_at: 2026-11-16T18:19:27.105Z
started_at: 2026-11-16T17:44:43.156Z
closed_at: 2026-11-16T18:19:27.104Z
close_reason: "Fixed in 9f22279b9 on PR #478 (head d9782d01e): waiting entry owns its controller; abandoned-request session step"
resolution: null
duplicate_of: null
---
Review A (round 1) of PR #478, https://github.com/jlevy/metabrowser/pull/478#pullrequestreview-5924265457. Severity: Low. Where: comparison-prefetch.js:430, :462-468, :145-149
