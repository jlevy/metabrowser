---
type: is
id: is-01m7v9twqbd4qg5jw2b2sshe5j
title: "PR #617 B1: a handle the server opens on a database or its -shm cancels SQLite's locks"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v9tw8y6ssgdghdyks2p5ty
hold: null
hold_until: null
created_at: 2026-11-20T01:41:16.138Z
updated_at: 2026-11-20T01:57:19.409Z
started_at: 2026-11-20T01:50:14.138Z
closed_at: 2026-11-20T01:57:19.408Z
close_reason: "fixed in 74df98ad5 (plan) and 7ef20c2f6 (measured): Decision 13 reader processes; lock hazard reproduced in access.json lock_cancelled_by_a_closed_handle; lock-hazard test added"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:412-414, 429-432, 494-498, 379-383. Raw opens for the race check, header reads, and magic check cancel the reader's POSIX locks in-process. Severity: High. PR #617. Review: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5986230518
