---
type: is
id: is-01m8ctxev3fsj2c86tpsrvadsq
title: Build shared structured-data tabs and navigation
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-structured-data-views.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8ctvgrty5asxe2xh62gzn8v
hold: null
hold_until: null
created_at: 2026-11-26T21:06:51.349Z
updated_at: 2026-11-26T22:18:13.647Z
started_at: 2026-11-26T21:23:14.382Z
---
Extract the core SDK mount and shared navigation, and enable Table, Tree and Source at the same address for YAML and JSON roots. Cover browserless history, focus and virtualized layouts.

## Notes

Standalone JSON/YAML and Markdown Frontmatter use the shared SDK Depth control (1–4, default 3). The one-request inline preview is capped at 100 total rows with balanced siblings; opening a value preserves its depth and focus on return. Twenty-four Universe People records at depth three showed median 34 and maximum 47 rows. The folder Table view now precedes Treemap. Browser and CLI tests passed. Canonical structured node addresses and full browser history remain.
