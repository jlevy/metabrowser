---
type: is
id: is-01m8a5xxha490zggra7e5b5780
title: "PR #847 A2: Retry repaints without disposing what the failed paint adopted"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8a5xvrkq70pj6kqvfd6916f
hold: null
hold_until: null
created_at: 2026-11-25T20:21:37.443Z
updated_at: 2026-11-25T20:21:47.723Z
started_at: 2026-11-25T20:21:47.720Z
---
Low. stack-page.js:1846-1853 Retry calls paintDiff without disposeBody(); the catch leaves an unadopted mounted view undisposed. PR #847, https://github.com/jlevy/metabrowser/pull/847#pullrequestreview-6064261954
