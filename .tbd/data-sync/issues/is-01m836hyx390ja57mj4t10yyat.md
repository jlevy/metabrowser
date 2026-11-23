---
type: is
id: is-01m836hyx390ja57mj4t10yyat
title: "Treemap: go deeper (owner asked 2026-11-22)"
kind: task
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T03:17:53.153Z
updated_at: 2026-11-23T05:31:43.438Z
started_at: 2026-11-23T03:18:27.312Z
closed_at: 2026-11-23T05:31:43.406Z
close_reason: "fixed in 30dba64cf and a3c7e040e: maxCells 1,600 and ROLLUP_MAX_NODES 4,000, measured; the Treemap on this repository nests seven levels where it stopped at five"
resolution: null
duplicate_of: null
---
Owner: can it go deeper? On the metabrowser repo (35,790 files incl. ignored) /api/rollup hits ROLLUP_MAX_NODES=1200 with 136 folders lazy at depth<=5; the compact map draws 124 cells and 0 files at 607x218; the full map 573-785 cells (maxCells 800). Measure where depth is lost (server node budget vs layout cell cap vs geometry) and raise the binding bound with measurements recorded beside the constant.
