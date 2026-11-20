---
type: is
id: is-01m7vmewd0gsvwcbdj9b7tw061
title: "PR #617 C6: the plan does not say who computes a watch's generation, or when a read samples its own"
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
created_at: 2026-11-20T04:46:56.928Z
updated_at: 2026-11-20T05:15:05.372Z
started_at: 2026-11-20T04:47:07.468Z
closed_at: 2026-11-20T05:15:05.372Z
close_reason: "fixed: 12cc8813d: generation() only stats and reads headers in the server process, the watch polls it, reads sample it before connecting; test added. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:273,448-460,603-607,613-614. Generation provider per kind (stat and bounded headers, never connects), polled in the server process; envelope generation sampled before connecting. Severity: Medium. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
