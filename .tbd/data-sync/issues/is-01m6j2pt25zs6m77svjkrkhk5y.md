---
type: is
id: is-01m6j2pt25zs6m77svjkrkhk5y
title: Clear inactive PR file selection without losing its retained cursor
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
created_at: 2026-11-04T01:27:50.591Z
updated_at: 2026-11-04T01:29:02.444Z
started_at: 2026-11-04T01:29:02.440Z
---
Whole-shell native Files navigation can leave an old manually expanded PR tree file blue/aria-selected after the page changes. Current file and roving keyboard anchor are separate: clear only the inactive page-selection mark, retain expansion/cursor. Reproduce exact installed7cabc native navigation, verify new active diff following and repeated-route/delayed-page ownership, then minimal panel fix with meaningful whole-route regression. Parent stopped publication; forward-only coordinator commit/gates/independent review required.
