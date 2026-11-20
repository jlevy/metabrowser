---
type: is
id: is-01m7vmet7aq16ht1vqc3v6sxae
title: "PR #617 C1: Decision 13 does not say how reader processes start, what crosses the pipe, or the deadlines"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7vme8z9g4zntjqcdkt3y0pe
hold: null
hold_until: null
created_at: 2026-11-20T04:46:54.697Z
updated_at: 2026-11-20T05:15:03.650Z
started_at: 2026-11-20T04:47:05.963Z
closed_at: 2026-11-20T05:15:03.647Z
close_reason: "fixed: 12cc8813d specifies reader processes (spawn, work unit, two deadlines, lifecycle, one-shot metab, platforms); process.json worker_cost. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:292,294-297,482-489,527-531,899-917. Start method (fork vs spawn), unit of work, handle bytes, CLI one-shot, three deadlines, kill leftovers, crash state, parent death, single-threaded vs watchdog, platforms. Severity: Medium. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
