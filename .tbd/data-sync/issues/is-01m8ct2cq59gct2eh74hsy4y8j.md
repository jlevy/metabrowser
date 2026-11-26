---
type: is
id: is-01m8ct2cq59gct2eh74hsy4y8j
title: Keep private local mirror paths out of Files page metadata
kind: bug
status: closed
priority: 1
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cqaes3exyw92wmaqqcr83n
hold: null
hold_until: null
created_at: 2026-11-26T20:52:04.450Z
updated_at: 2026-11-26T21:05:20.576Z
started_at: 2026-11-26T20:52:06.607Z
closed_at: 2026-11-26T21:05:20.550Z
close_reason: "Implemented and independently reviewed in merged Metabrowser PR #892. Exact-head CI passed."
resolution: null
duplicate_of: null
---
The pinned-mirror exclusion test caught a local origin’s path in source-tooltip HTML. Keep the real resolved path on an actual working tree and keep cloud and local mirror metadata within the viewer trust boundary.
