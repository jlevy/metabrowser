---
type: is
id: is-01m75d7s32vnbfnvrn84paq6pt
title: "PR #348 F2: the task-item cap misses task items behind a quote or a second list marker"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75d7enb9z11kt1ge773zz3r
hold: null
hold_until: null
created_at: 2026-11-11T13:37:26.625Z
updated_at: 2026-11-11T14:23:39.793Z
started_at: 2026-11-11T13:37:36.316Z
closed_at: 2026-11-11T14:23:39.792Z
close_reason: "Fixed: d52784f7. Task items count after any mix of quote and list markers and on a line after a bare marker. 1,024 quoted items render 194 ms; the 1,025th is refused. Tests: costly-shape test (quoted, nested), misread test (cr, blank-first, quote-in-list)."
resolution: null
duplicate_of: null
---
Review F2 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858785036): 2,500 '> - [ ] a' items estimated 400 ms, rendered 773 ms; 1,206 ms with paragraph padding.
