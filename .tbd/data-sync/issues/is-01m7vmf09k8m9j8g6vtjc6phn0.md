---
type: is
id: is-01m7vmf09k8m9j8g6vtjc6phn0
title: "PR #617 C15: say what the reader process boundary is (not a sandbox); bound worker memory"
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
created_at: 2026-11-20T04:47:00.915Z
updated_at: 2026-11-20T05:15:08.397Z
started_at: 2026-11-20T04:47:10.263Z
closed_at: 2026-11-20T05:15:08.397Z
close_reason: "fixed: 12cc8813d states the reader process is crash isolation, not a sandbox, with a setrlimit memory bound. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:730-732. Suggestion. Severity: Suggestion. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
