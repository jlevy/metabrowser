---
type: is
id: is-01m6j331jhmbnr4wdhjpf03pvs
title: Replay the active diff selection on repeated same-page route notices
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: pulls_navigation
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-04T01:34:31.503Z
updated_at: 2026-11-04T01:37:39.124Z
started_at: 2026-11-04T01:37:39.123Z
---
Independent real mounted file-row probe at7cabc shows same-page setCurrent(number,null) clears1→0 selected file because followCurrentFile skips unchanged handle. Replay/preserve an owned current observation at route boundary, guard stale page/PR callbacks, retain explicit non-null file precedence and null/unavailable jump behavior. Cohesive fix with mb-l5il; real pagehost/history and delayed subscription controls, external whole-shell reproduction, independent recheck and fresh artifact gates required.
