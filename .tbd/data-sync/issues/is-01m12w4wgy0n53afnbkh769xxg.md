---
type: is
id: is-01m12w4wgy0n53afnbkh769xxg
title: "R3: name the Phase 2 primitives that GitHub acquisition actually needs"
kind: chore
status: open
priority: 1
version: 1
spec_path: docs/project/reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md
labels: []
dependencies: []
parent_id: is-01m12w4tz60cps1t8d6z1v4zet
created_at: 2026-08-28T00:26:06.237Z
updated_at: 2026-08-28T00:26:06.237Z
---
The dependency map gives Phase 5 '2 job/storage primitives, 4 schemas', but Phase 2 and Phase 3 are absent from the stated priorities. Either provider work silently includes the generic catalog, refresh, repair and purge, or it depends on primitives that will not exist. Identify the exact primitives (likely job progress/cancellation/stage outcomes plus atomic storage publication) and either extract them into a small phase the provider work can carry, or insert Phase 2 into the priority order explicitly.
