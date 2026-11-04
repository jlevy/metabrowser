---
type: is
id: is-01m6hyepsg0bryhdsbn1fkre3b
title: Clarify PR number, author, and branch typography
kind: feature
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: pulls_navigation
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-04T00:13:30.799Z
updated_at: 2026-11-04T00:28:15.968Z
started_at: 2026-11-04T00:13:49.199Z
---
Owner asks sidebar PR number in normal row size/dark text, author same normal size in muted gray, branches smaller. Main page PR number should use dark title ink at existing title size. Split metadata spans without changing navigation/row identity; check actual browser baseline/variable-height measurement after styling.

## Notes

Owner-requested hierarchy implemented: dark normal-size sidebar PR numbers, bold muted usernames at each surface normal text size, smaller branch names using consistent remote-ref color; main h1 number dark at unchanged title size. Semantic metadata spans and DOM assertions added; design-system documentation updated. Focused61 tests13.86s and both browser type gates/lint pass. Source frozen; final-wheel browser QA must record current collapsed-row height/spacer behavior at5000 and narrow/wide alignment, not reuse old timing/41.5px claim.
