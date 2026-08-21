---
type: is
id: is-01m0jsxf4dfd6v9ncxatvm6ret
title: Goldens for /api/rollup, including truncated and pending subtrees
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:15.084Z
updated_at: 2026-08-21T18:39:15.084Z
---
The rollup feeds both folder views, Overview and Treemap. Cover a complete subtree, one truncated by the node budget (children retained alongside a rest bucket), and one still pending while the walk converges, since the client renders those three states differently.
