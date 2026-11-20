---
type: is
id: is-01m7vmetmtcq4vv8nzen7aczpf
title: "PR #617 C2: the capped count is validated with the page, which makes the reader lock"
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
created_at: 2026-11-20T04:46:55.130Z
updated_at: 2026-11-20T05:15:03.998Z
started_at: 2026-11-20T04:47:06.253Z
closed_at: 2026-11-20T05:15:03.998Z
close_reason: "fixed: 7ac84d81e and 12cc8813d validate page and count apart; contention.json rerun, 0 refused commits, page valid 15/15 at every pace; Decision 10 restated. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:513-516,533-536,861-870; explorations/sqlite-guest-reads/measure.py:859-876. Validate page and count apart; count with no wait falls back to estimate; rerun contention and restate Decision 10. Severity: Medium. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
