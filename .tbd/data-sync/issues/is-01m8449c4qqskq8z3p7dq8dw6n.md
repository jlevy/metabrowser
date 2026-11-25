---
type: is
id: is-01m8449c4qqskq8z3p7dq8dw6n
title: "Treemap layer 5: denser rollup (nodes=, ignored=exclude, compact encoding)"
kind: feature
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/754
    at: 2026-11-23T14:37:23.266Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T11:57:29.110Z
updated_at: 2026-11-25T02:15:34.589Z
started_at: 2026-11-23T11:57:35.644Z
closed_at: 2026-11-25T02:15:34.582Z
close_reason: "Landed in #754 (treemap stack layer 5), merged to main."
resolution: null
duplicate_of: null
---
Phase 2 of the treemap canvas plan: /api/rollup gains nodes= (bounded by a raised ROLLUP_MAX_NODES; default unchanged), ignored=exclude (gitignored entries take no budget), encoding=compact (file children as positional arrays), top tied to the budget so one flat folder cannot take it, and a byte bound on the rollup body cache. The Treemap view asks for them and decodes in the folder plugin; Show ignored then refetches.

## Notes

PR #754 is open (stack #725, layer 5), not merged: the user tests it first. Local verify: every tier passed except 3 known failures (mb-vk94, mb-tejh, mb-3ypb).
