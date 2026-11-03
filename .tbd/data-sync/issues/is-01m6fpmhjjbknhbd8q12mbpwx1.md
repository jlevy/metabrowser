---
type: is
id: is-01m6fpmhjjbknhbd8q12mbpwx1
title: "PR #283 D4: the forward merge dropped filesUnavailableText and the second-session evidence from the map"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T03:18:24.593Z
updated_at: 2026-11-03T03:28:53.747Z
started_at: 2026-11-03T03:18:37.432Z
closed_at: 2026-11-03T03:28:53.745Z
close_reason: "fixed in 0098e113 on PR #283: D4 filesUnavailableText and second-session evidence restored in the map"
resolution: null
duplicate_of: null
---
Low. Review D, PR #283, https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5746541377. docs/project/architecture/arch-views-models-routes.md, rows github.pull-page-paint-decisions and github.pull-page-place: 85da786 resolved them to the base's rows plus keyMovesPane, dropping builtin_plugins/github/pull-page.js#filesUnavailableText and node tests/dom/github-pull-page-second-session.js that dac71d0 had.
