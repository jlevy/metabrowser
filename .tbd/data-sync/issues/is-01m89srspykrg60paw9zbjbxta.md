---
type: is
id: is-01m89srspykrg60paw9zbjbxta
title: "Pulls rows: one wrapping run with the author before the diff summary (no separate byline)"
kind: task
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T16:49:06.770Z
updated_at: 2026-11-25T16:50:16.201Z
started_at: 2026-11-25T16:49:30.580Z
---
User follow-up to mb-pw8t: 'The author should be before the diff and everything should wrap', then 'Actually, the diff can be on its own line. That will be cleaner.' Row: one inline run that wraps with the hanging indent: title · 5/12 (stack members) · #N · author · age; then the diff summary and chevron (+a −b ›) on a line of their own, aligned with the text column. The summary and chevron remain the only toggle; any other click selects; the lines' room stays reserved. Remeasure line counts at 299/380/420 px, update ROW_ESTIMATE_PX, goldens, Chrome row-lines checks, design-system.md, reviewing-pull-requests.md and the unreleased changelog fragments.
