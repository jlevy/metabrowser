---
type: is
id: is-01m8449c4qqskq8z3p7dq8dw6n
title: "Treemap layer 5: denser rollup (nodes=, ignored=exclude, compact encoding)"
kind: feature
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T11:57:29.110Z
updated_at: 2026-11-23T11:57:35.645Z
started_at: 2026-11-23T11:57:35.644Z
---
Phase 2 of the treemap canvas plan: /api/rollup gains nodes= (bounded by a raised ROLLUP_MAX_NODES; default unchanged), ignored=exclude (gitignored entries take no budget), encoding=compact (file children as positional arrays), top tied to the budget so one flat folder cannot take it, and a byte bound on the rollup body cache. The Treemap view asks for them and decodes in the folder plugin; Show ignored then refetches.
