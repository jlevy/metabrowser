---
type: is
id: is-01m7vmey4hbs8ybdwnx5q7axht
title: "PR #617 C10: the reader below SQLite 3.43 is a second code path nothing can test"
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
created_at: 2026-11-20T04:46:58.705Z
updated_at: 2026-11-20T05:15:06.783Z
started_at: 2026-11-20T04:47:08.691Z
closed_at: 2026-11-20T05:15:06.783Z
close_reason: "fixed: 12cc8813d makes SQLite 3.43 the reader's minimum; the fallback path is removed. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:559-565. Make 3.43 the minimum, or name the CI job that runs an older library. Severity: Low. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
