---
type: is
id: is-01m0ycrwkzbfjdbf19t8tpevjp
title: Make navigation tooltips pointer-only and dismiss them on keyboard selection
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T06:40:26.744Z
updated_at: 2026-08-26T07:43:11.268Z
closed_at: 2026-08-26T07:43:11.266Z
close_reason: Implemented pointer-only delegated and Git commit tooltips with immediate focus/keyboard dismissal and stale-hover suppression. Focused DOM/design tests, make verify, and exact installed-build browser validation pass; pointer behavior was visibly validated on ad7c8b7 and the final 4d45e0d changes do not touch that path.
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/static/git-panel.js renderRow, handleCommitRowKeydown, scheduleHover, cancelHover, and a focused tooltip-dismissal seam; tests/dom/git-panel-behavior.js tooltip and keyboard cases; docs/design-system.md navigation-tooltip contract; docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md implementation table/phase; CHANGELOG.md. Behavior/invariants: commit-summary tooltips open only from stable pointer hover; focus alone never opens or retains one; Arrow Up/Down and Enter/Space immediately dismiss pending or visible tooltip presentation before selection; stale async hover completion cannot reopen a tooltip after keyboard intent; pointer preparation remains bounded/cancellable and file-tree navigation keeps its existing pointer-only behavior; accessible names and selection semantics remain unchanged. Acceptance: focused tests cover hover show/leave, focus suppression, keyboard dismissal, stale async suppression, and unchanged Arrow navigation; design-system checks bind the documented rule; make format and make verify pass; visible-browser pointer and keyboard smoke tests pass.
