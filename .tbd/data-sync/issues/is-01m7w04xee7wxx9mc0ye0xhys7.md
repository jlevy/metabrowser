---
type: is
id: is-01m7w04xee7wxx9mc0ye0xhys7
title: "PR #649 A4: agent-log payload change has no test; stale comments"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7w04vfg21q09dmkkdsmbzwp
hold: null
hold_until: null
created_at: 2026-11-20T08:11:13.229Z
updated_at: 2026-11-20T08:47:33.040Z
started_at: 2026-11-20T08:11:20.888Z
closed_at: 2026-11-20T08:47:33.039Z
close_reason: "fixed in c7b48c7db: log-event-row session pins the four payload invariants; comments corrected; CI run 44703997703 green at 70f180380153ea5a6531e32e219e4ddf2d427883"
resolution: null
duplicate_of: null
---
Medium. builtin_plugins/agent_log/index.js:174-222; app.js:7372-7375; tests/dom/log-event-row-session.js. Review: https://github.com/jlevy/metabrowser/pull/649#pullrequestreview-5989412950
