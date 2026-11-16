---
type: is
id: is-01m7jqbtydrkafn5s7247x5mcs
title: "PR #478 A6: queued warms keep running after the Pulls panel is hidden or offline"
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
created_at: 2026-11-16T17:44:32.972Z
updated_at: 2026-11-16T18:19:27.817Z
started_at: 2026-11-16T17:44:44.149Z
closed_at: 2026-11-16T18:19:27.816Z
close_reason: "Fixed in 9f22279b9 on PR #478 (head d9782d01e): stopWarming on hide, park, offline; warmStops in the comparisons story"
resolution: null
duplicate_of: null
---
Review A (round 1) of PR #478, https://github.com/jlevy/metabrowser/pull/478#pullrequestreview-5924265457. Severity: Low. Where: comparison-prefetch.js:560, :580, pulls-panel.js:4513, :2134-2149
