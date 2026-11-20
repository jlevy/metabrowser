---
type: is
id: is-01m7vmezev955gq5w4c9b74frf
title: "PR #617 C13: materialize a pinned database once instead of deserializing it"
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
created_at: 2026-11-20T04:47:00.059Z
updated_at: 2026-11-20T05:15:07.761Z
started_at: 2026-11-20T04:47:09.647Z
closed_at: 2026-11-20T05:15:07.760Z
close_reason: "fixed: 12cc8813d writes a Git blob once to a private folder keyed by object id and reads it immutable=1; deserialization removed. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:297,503. Suggestion. Severity: Suggestion. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
