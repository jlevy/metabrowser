---
type: is
id: is-01m87byqxtqaq9bayypy2bccx0
title: "PR #771 A2: a tick plus a word edit in one item loses its word marks"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87bxfh1ymbm8c10h6rzs8gx
hold: null
hold_until: null
created_at: 2026-11-24T18:09:12.629Z
updated_at: 2026-11-24T18:14:03.345Z
started_at: 2026-11-24T18:14:03.344Z
---
Low. src/metabrowser/diff/markdown_projection.py:1554-1595 (_inline_change): an input pair differing only in checked fails the equal-attributes test, so the item is drawn removed and added without word marks. PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578
