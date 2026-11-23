---
type: is
id: is-01m836hyx390ja57mj4t10yyat
title: "Treemap: go deeper (owner asked 2026-11-22)"
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T03:17:53.153Z
updated_at: 2026-11-23T03:18:27.358Z
started_at: 2026-11-23T03:18:27.312Z
---
Owner: can it go deeper? On the metabrowser repo (35,790 files incl. ignored) /api/rollup hits ROLLUP_MAX_NODES=1200 with 136 folders lazy at depth<=5; the compact map draws 124 cells and 0 files at 607x218; the full map 573-785 cells (maxCells 800). Measure where depth is lost (server node budget vs layout cell cap vs geometry) and raise the binding bound with measurements recorded beside the constant.
