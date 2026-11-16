---
type: is
id: is-01m7h0xm83svdvaxjvjr2x4hzw
title: "PR #455 C2: server-time.mjs cuts each window's log at the file's size, not at a line's end"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:53:04.258Z
updated_at: 2026-11-16T01:53:19.765Z
started_at: 2026-11-16T01:53:19.764Z
---
Severity: Low. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review C (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914139612), finding C2. References: explorations/performance-loop/server-time.mjs:196-206, :286-298, :339-352, :385-392.
