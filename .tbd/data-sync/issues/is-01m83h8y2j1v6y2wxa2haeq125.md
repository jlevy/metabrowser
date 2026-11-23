---
type: is
id: is-01m83h8y2j1v6y2wxa2haeq125
title: "Treemap granularity: draw the hundreds of children large folders hold"
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/752
    at: 2026-11-23T11:16:32.433Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T06:25:11.761Z
updated_at: 2026-11-23T11:16:32.442Z
started_at: 2026-11-23T06:30:58.691Z
---
Owner asked 2026-11-22: large boxes with hundreds of subcomponents draw as a few cells. Measured on this repository at 1223x587 (Files, Show ignored on): 584 cells drawn of 4,000 nodes sent; 464 folders unexpanded by the node budget (node_modules/zod 840 files, @highlightjs 892, drawn solid at ~120x130); top=200 folds 351 of tests/ files into a remainder; 35,790 files over 718k px2 is ~20 px2 a file, under the 4 px DOM cell floor. Candidate: canvas renderer down to 1 px with hit testing, plus a compact or lazily deepened tree from the server.
