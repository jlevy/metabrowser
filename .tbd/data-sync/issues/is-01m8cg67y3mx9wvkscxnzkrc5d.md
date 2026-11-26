---
type: is
id: is-01m8cg67y3mx9wvkscxnzkrc5d
title: Mark SQLite reverse counts incomplete for previewed target values
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
labels: []
dependencies: []
parent_id: is-01m8bmwx2pehff86p5zd3v6e5t
created_at: 2026-11-26T17:59:24.858Z
updated_at: 2026-11-26T17:59:24.858Z
---
PR #882 correctness review reproduced a false exact zero for referencing an oversized UNIQUE value. Preserve SQLite limits while reporting a lower bound.
