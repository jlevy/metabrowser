---
type: is
id: is-01kzmqezx2bsks2axpcxpykd55
title: "PR #26 review R2: listeners receive a stale snapshot after a re-entrant write"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
parent_id: is-01kzmqed5sgcx3nj3kfzqrjwga
created_at: 2026-08-10T02:19:10.625Z
updated_at: 2026-08-10T02:30:24.042Z
closed_at: 2026-08-10T02:30:24.042Z
close_reason: "Fixed in 6f4e676. R1: notification is invalidation-only; 149ms to 0.01ms per mutation at 500k with an idle subscriber; structural guard verified to fail if a payload returns. R2: dissolved by R1, re-entrancy pinned from the listener side. R3: plan split into closed vs still-open limits. R4: disposal test asserts the listener list is empty (verified failing without the unsubscribe) and exercises timer cleanup. make verify green, 785 tests."
---
known_file_catalog.js:93. bumpRevision() computes the snapshot once before invoking listeners. If an earlier listener mutates the catalog, the nested bump increments revision and returns early on notifyDepth > 0, so later listeners still receive the pre-write snapshot and nothing repairs their view. Reviewer reproduced: listener A adds nested.txt, listener B sees revision/count 1/1 while catalog.snapshot() is already 2/2. That contradicts the JSDoc and .d.ts contract this PR added, which promises listeners receive the snapshot containing the change.

Fix: the projection-free API from R1 removes this contract entirely. If a payload were retained instead, the snapshot would have to be computed per listener invocation while keeping the no-reentry guarantee.
