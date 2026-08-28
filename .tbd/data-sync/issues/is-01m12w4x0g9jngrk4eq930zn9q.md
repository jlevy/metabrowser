---
type: is
id: is-01m12w4x0g9jngrk4eq930zn9q
title: "R4: size Phase 1A and decide what the first cache release actually needs"
kind: chore
status: closed
priority: 2
version: 2
spec_path: docs/project/reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md
labels: []
dependencies: []
parent_id: is-01m12w4tz60cps1t8d6z1v4zet
created_at: 2026-08-28T00:26:06.734Z
updated_at: 2026-08-28T02:28:24.775Z
closed_at: 2026-08-28T02:28:24.773Z
close_reason: "Done in f46bc26: Phase 1A now separates what it cannot defer (identity, atomic publication, locking, honest state, CACHEDIR.TAG, reclamation sweep) from what it may (migration harness, format history beyond f01, compiled-schema drift), with deferral required to be a recorded decision."
resolution: null
duplicate_of: null
---
Phase 1A must land before any repository is cloned: app-home resolver, config.yml, layout.yml, format history, future-format failure, migration harness, SoftSchema adoption plus supply-chain exemption, compiled schemas, drift/corpus/inventory/wheel checks, atomic YAML, locking, quarantine, trash, CACHEDIR.TAG, startup sweep. The released-data-from-day-one argument is sound, but the phase is unestimated and stands between the goal and any visible result. Size it; if it is large, the trim candidates are the parts that only pay off once a second reader exists (migration harness, format history, compiled-schema drift). Identity, atomic publication, locking, and honest state are not optional.
