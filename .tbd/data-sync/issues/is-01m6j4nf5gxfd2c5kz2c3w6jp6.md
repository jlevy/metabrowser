---
type: is
id: is-01m6j4nf5gxfd2c5kz2c3w6jp6
title: Use shared subdued colors for all Git file status letters
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T02:02:03.823Z
updated_at: 2026-11-04T02:56:01.597Z
started_at: 2026-11-04T02:28:29.823Z
---
A consistent A/D/M/R/C/T/U/? presentation across Git file lists, commit summaries, diff headers and PR file trees; green additions, red deletions, dark yellow modifications, other conventional semantic states. Audit existing theme roles and GitHub Primer primary guidance; reuse shared tokens and ensure contrast in light/dark. Preserve letters/tooltips and counts; avoid bright per-location literals.

## Notes

Implemented shared file-change-status raw semantic markers and theme roles across Git summary/file list, diff headers and PR trees. Same-glyph unchanged-to-modified retained-row regression added. Focused contrast checks cover normal/sidebar/hover; selected-ground source diagnostic retained. Frontend freeze v4 recorded under design-tokens-14433032; independent/final installed-wheel checks pending coordinator.
