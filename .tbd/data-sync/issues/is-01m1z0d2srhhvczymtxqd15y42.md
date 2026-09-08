---
type: is
id: is-01m1z0d2srhhvczymtxqd15y42
title: Make coordinator shutdown joinable and cancellation-safe
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T22:39:13.190Z
updated_at: 2026-09-08T00:02:43.670Z
closed_at: 2026-09-08T00:02:43.668Z
close_reason: Coordinator now owns one shielded shutdown task and every close joins it. Deterministic tests cover a held provider read and cancellation of the first close caller.
resolution: null
duplicate_of: null
---
InventoryCoordinator.close sets _closed before draining active operations. While its Condition wait releases the lock, a concurrent close sees _closed and returns before the provider is closed. Cancelling that first close leaves _closed true with a live handle, and later close calls cannot recover. Use one owned shutdown task, joined under shield by every close caller; regress with a gated provider read and cancellation.
