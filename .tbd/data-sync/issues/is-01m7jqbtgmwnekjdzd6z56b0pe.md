---
type: is
id: is-01m7jqbtgmwnekjdzd6z56b0pe
title: "PR #478 A5: warmer record reads feed the server recently-viewed list"
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
created_at: 2026-11-16T17:44:32.532Z
updated_at: 2026-11-16T18:19:27.453Z
started_at: 2026-11-16T17:44:43.518Z
closed_at: 2026-11-16T18:19:27.452Z
close_reason: "Fixed in 9f22279b9 on PR #478 (head d9782d01e): warm=1 skips note_viewed; test_a_warm_read_answers_the_record_and_is_not_a_view and golden steps"
resolution: null
duplicate_of: null
---
Review A (round 1) of PR #478, https://github.com/jlevy/metabrowser/pull/478#pullrequestreview-5924265457. Severity: Low. Where: pulls-panel.js:4497-4505, sidekick.py:196-200, pull_prefetch.py:202-224
