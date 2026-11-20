---
type: is
id: is-01m7v68wh60hn32we7m6ec3bk2
title: "PR #617 A1: access table misses stale and partial sidecar states; immutable=1 drops committed data"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v68w30f9d3dts3s8ga3rkz
hold: null
hold_until: null
created_at: 2026-11-20T00:39:00.390Z
updated_at: 2026-11-20T00:58:44.496Z
started_at: 2026-11-20T00:39:15.618Z
closed_at: 2026-11-20T00:58:44.496Z
close_reason: "fixed in `d5ea44d`: the access table keys on the `-wal` size at the resolved path; `immutable=1` only with no or a zero-byte `-wal`, a log with frames that cannot be read without writing (no `-shm`, or several hard links) is shown as the checkpointed state with \"N bytes of write-ahead log not included\"; \"owner is live\" dropped from the Info view; each state is a nondestructive test case. Every row of the finding's table reproduced in `explorations/sqlite-guest-reads` (`fda5f4c`, results/access.json)"
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 163-168, 336-342, 508-513. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A1).
