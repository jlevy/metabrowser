---
type: is
id: is-01kzmqf0bxehdqmkgnyrystg59
title: "PR #26 review R3: plan contradicts itself about query convergence"
kind: task
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
parent_id: is-01kzmqed5sgcx3nj3kfzqrjwga
created_at: 2026-08-10T02:19:11.100Z
updated_at: 2026-08-10T02:30:24.050Z
closed_at: 2026-08-10T02:30:24.050Z
close_reason: "Fixed in 6f4e676. R1: notification is invalidation-only; 149ms to 0.01ms per mutation at 500k with an idle subscriber; structural guard verified to fail if a payload returns. R2: dissolved by R1, re-entrancy pinned from the listener side. R3: plan split into closed vs still-open limits. R4: disposal test asserts the listener list is empty (verified failing without the unsubscribe) and exercises timer cleanup. make verify green, 785 tests."
---
plan-2026-07-17-scalable-file-search.md:682. Phase 2.1 says an open query re-runs as coverage changes, but the later remaining-limits list still says new files appear only after another input change or a palette reopen. Fix the bullet, and while there separate historical Phase 1 findings from limits that actually remain after Phase 2/2.1 so future work does not treat completed work as open.
