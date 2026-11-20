---
type: is
id: is-01m7vmex7t1kfw1sxf7tacsspe
title: "PR #617 C8: validation of a write-ahead-log main file rests on size and mtime alone"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7vme8z9g4zntjqcdkt3y0pe
hold: null
hold_until: null
created_at: 2026-11-20T04:46:57.786Z
updated_at: 2026-11-20T05:15:06.056Z
started_at: 2026-11-20T04:47:08.069Z
closed_at: 2026-11-20T05:15:06.056Z
close_reason: "fixed: 12cc8813d adds -wal mtime, racy-mtime rule, main-before-wal copy order; generation.json distinct_main_file_change_counters=2 of 200 cycles. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:507-512. WAL change counter does not move; racy-mtime rule; add -wal mtime; copy main file before -wal. Severity: Low. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
