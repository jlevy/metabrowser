---
type: is
id: is-01kzmqf0v4xs8pkzpc81vd919e
title: "PR #26 review R4: disposal test does not observe the subscription"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
parent_id: is-01kzmqed5sgcx3nj3kfzqrjwga
created_at: 2026-08-10T02:19:11.587Z
updated_at: 2026-08-10T02:30:24.063Z
closed_at: 2026-08-10T02:30:24.063Z
close_reason: "Fixed in 6f4e676. R1: notification is invalidation-only; 149ms to 0.01ms per mutation at 500k with an idle subscriber; structural guard verified to fail if a payload returns. R2: dissolved by R1, re-entrancy pinned from the listener side. R3: plan split into closed vs still-open limits. R4: disposal test asserts the listener list is empty (verified failing without the unsubscribe) and exercises timer cleanup. make verify green, 785 tests."
---
tests/dom/search_palette_behavior.js:807. The 'dispose unsubscribes from the catalog' check emits a change and asserts no search request, but it still passes with unsubscribeCatalog() deleted, because the retained callback returns early on disposed. It does not protect the disposal path it names.

Fix: assert catalogListeners.length === 0 immediately after dispose, and schedule a refresh before close/dispose so the pending-timer cleanup is exercised rather than the early-return guard.
