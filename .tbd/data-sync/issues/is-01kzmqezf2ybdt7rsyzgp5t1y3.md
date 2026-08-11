---
type: is
id: is-01kzmqezf2ybdt7rsyzgp5t1y3
title: "PR #26 review R1: catalog notification builds a sorted snapshot per mutation"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
parent_id: is-01kzmqed5sgcx3nj3kfzqrjwga
created_at: 2026-08-10T02:19:10.177Z
updated_at: 2026-08-10T02:30:24.021Z
closed_at: 2026-08-10T02:30:24.005Z
close_reason: "Fixed in 6f4e676. R1: notification is invalidation-only; 149ms to 0.01ms per mutation at 500k with an idle subscriber; structural guard verified to fail if a payload returns. R2: dissolved by R1, re-entrancy pinned from the listener side. R3: plan split into closed vs still-open limits. R4: disposal test asserts the listener list is empty (verified failing without the unsubscribe) and exercises timer cleanup. make verify green, 785 tests."
---
known_file_catalog.js:86 and :93, app.js:4070. initQuickFileFinder installs the palette subscriber for the application lifetime, so subscribers.length is nonzero even with the overlay hidden and every bumpRevision() calls snapshot(), which copies and sorts the whole catalog. That bypasses the palette's 150ms coalescing window and makes every live delta, navigation, tree update, and resync an O(n log n) main-thread projection — while the palette is closed, which is the common case.

Reviewer measured one upsert into a 500,000-file catalog at 53.3ms with an idle no-op subscriber versus 0.1ms without (100k: ~6ms vs ~0ms).

Fix: make the subscription a lightweight invalidation signal (no argument, or just the revision) and let the palette's coalesced callback take a snapshot only when it renders status or starts a search. subscribe() is new in this PR and the only production listener ignores the payload, so there is no compatibility cost. Add a regression proving an idle listener does not trigger the sorted projection.
