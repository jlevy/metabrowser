---
type: is
id: is-01m7vmev3rdt62d3zsmsar8jrd
title: "PR #617 C3: the locked fallback answers a different query than the one asked"
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
created_at: 2026-11-20T04:46:55.608Z
updated_at: 2026-11-20T05:15:04.388Z
started_at: 2026-11-20T04:47:06.561Z
closed_at: 2026-11-20T05:15:04.388Z
close_reason: "fixed: 12cc8813d removes the locked fallback by adopting C11 (never lock a rollback database). Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:341-362,499,515-516. Key-ordered fallback ignores the requested sort, filter, search, or cursor. Severity: Medium. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
