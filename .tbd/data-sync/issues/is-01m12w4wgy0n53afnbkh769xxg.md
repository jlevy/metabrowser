---
type: is
id: is-01m12w4wgy0n53afnbkh769xxg
title: "R3: name the Phase 2 primitives that GitHub acquisition actually needs"
kind: chore
status: closed
priority: 1
version: 2
spec_path: docs/project/reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md
labels: []
dependencies: []
parent_id: is-01m12w4tz60cps1t8d6z1v4zet
created_at: 2026-08-28T00:26:06.237Z
updated_at: 2026-08-28T02:28:24.263Z
closed_at: 2026-08-28T02:28:24.262Z
close_reason: "Done in f46bc26: the provider plan names exactly what it needs from the cache in a table (published entry, atomic publication, locking, job lifecycle, core ref fetching) and states that catalog, chooser, purge, and size accounting are NOT prerequisites, with the small extraction called out if scheduling requires it."
resolution: null
duplicate_of: null
---
The dependency map gives Phase 5 '2 job/storage primitives, 4 schemas', but Phase 2 and Phase 3 are absent from the stated priorities. Either provider work silently includes the generic catalog, refresh, repair and purge, or it depends on primitives that will not exist. Identify the exact primitives (likely job progress/cancellation/stage outcomes plus atomic storage publication) and either extract them into a small phase the provider work can carry, or insert Phase 2 into the priority order explicitly.
