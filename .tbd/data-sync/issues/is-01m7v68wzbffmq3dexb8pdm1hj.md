---
type: is
id: is-01m7v68wzbffmq3dexb8pdm1hj
title: "PR #617 A2: stat-then-open race, reader-closes-last, symlinks and hard links create or miss sidecars"
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
created_at: 2026-11-20T00:39:00.843Z
updated_at: 2026-11-20T00:58:44.798Z
started_at: 2026-11-20T00:39:15.955Z
closed_at: 2026-11-20T00:58:44.798Z
close_reason: "fixed in `d5ea44d`: real path resolved before any sidecar stat (also for the watch); more than one hard link reads as stale-but-labelled; a race check opens the `-shm` first and compares identity after connecting, reporting sidecars created by an owner that exited; Goals state the reader-closes-last residual; staged tests for each case. Reproduced in `fda5f4c` (owner exits between stat and open, reader closes last, symlink); the hard-link case reproduced as a silent stale read that created `hard.db-wal`/`hard.db-shm` rather than `SQLITE_IOERR_SHORT_READ`, so the finding stands with a timing-dependent outcome"
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 48-50, 333-341, 588-593. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A2).
