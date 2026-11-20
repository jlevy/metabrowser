---
type: is
id: is-01m7h0xjthfz5t19t0sydzgvpj
title: "PR #455 B11: report how long the event loop was held over a window (loop-lag sampler)"
kind: bug
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7wysap12x9d1xp4zz3m4sds
hold: null
hold_until: null
created_at: 2026-11-16T01:53:02.800Z
updated_at: 2026-11-20T17:11:52.284Z
started_at: 2026-11-16T01:53:18.593Z
---
Severity: Suggestion. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review B (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305), finding B11. References: src/metabrowser/server.py; explorations/performance-loop/server-time.mjs.

## Notes

Deferred from PR #455 review B, B11 (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305). A loop-lag sampler in the server, its maximum and total written to the verbose log and read by server-time.mjs beside busy and the CPU time server-time/3 now records. New server instrumentation; waits on exp-095's protocol (mb-9uyq) deciding whether CPU time alone separates (a)'s move of compression off the event loop.
