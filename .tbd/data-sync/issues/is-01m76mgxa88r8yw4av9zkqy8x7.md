---
type: is
id: is-01m76mgxa88r8yw4av9zkqy8x7
title: "PR #341 D1: exit waiters resume before ChildOwnership records the exit"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76mgk23q075j4w3wjjg27a0
hold: null
hold_until: null
created_at: 2026-11-12T01:04:00.326Z
updated_at: 2026-11-12T01:31:24.643Z
started_at: 2026-11-12T01:04:10.684Z
closed_at: 2026-11-12T01:31:24.642Z
close_reason: "fixed in ed59adee (pushed, head 358cebd5): ChildOwnership.exited(announce:) records the exit before resuming waiters; ChildOwnershipTests fail with the old order, pass now. Disposition: https://github.com/jlevy/metabrowser/pull/341#issuecomment-6811709019"
resolution: null
duplicate_of: null
---
Severity Medium. PR #341, review D (https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5867388071). apps/macos/Sources/ShellCore/Supervision/ServerProcess.swift:214 resolves the exit latch before ownership.exited() at :216, so a waiter resumed by waitForExit() can call release() while ChildOwnership.State.exited is false: release does not reap, and a later signalGroup still reaches the group. Makes SpawnedPidOwnershipTests.anExitedChildKeepsItsPidUntilReleased and noSignalLeavesAfterRelease (Tests/ShellCoreTests/PidOwnershipTests.swift:149,180) scheduling-dependent. Fix: record the exit before resolving the latch; deterministic interleaving test; keep the signal/reap lock and the process-group sweep.
