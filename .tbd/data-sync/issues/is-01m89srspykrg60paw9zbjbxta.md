---
type: is
id: is-01m89srspykrg60paw9zbjbxta
title: "Pulls rows: one wrapping run with the author before the diff summary (no separate byline)"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T16:49:06.770Z
updated_at: 2026-11-25T16:49:06.770Z
---
User follow-up to mb-pw8t: 'The author should be before the diff and everything should wrap.' Fold the separate author/age line into the row's single inline run, which wraps with the hanging indent: title · 5/12 (stack members) · #N · author · age · +a −b ›. The diff summary and chevron stay last and remain the only toggle; any other click selects. Remeasure line counts at 299/380/420 px and update ROW_ESTIMATE_PX, goldens, Chrome row-lines checks, design-system.md, reviewing-pull-requests.md and the unreleased changelog fragments.
