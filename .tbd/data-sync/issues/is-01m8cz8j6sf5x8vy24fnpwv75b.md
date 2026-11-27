---
type: is
id: is-01m8cz8j6sf5x8vy24fnpwv75b
title: Prevent background Commit preparation from leaking a replay spool on abrupt exit
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/898
    at: 2026-11-26T22:37:16.016Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cygycfcqc68hze2j13qhc7
hold: null
hold_until: null
created_at: 2026-11-26T22:22:49.560Z
updated_at: 2026-11-26T22:37:16.023Z
started_at: 2026-11-26T22:23:57.370Z
---
Independent review found that Ctrl-C or hangup exits the server without lifespan cleanup, leaving a named history spool after automatic startup. Use an anonymous temporary file, consume the serve-only intent, and keep temp-storage refusal isolated from app shutdown.
