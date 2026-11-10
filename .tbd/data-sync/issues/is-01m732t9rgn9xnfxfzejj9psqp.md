---
type: is
id: is-01m732t9rgn9xnfxfzejj9psqp
title: Coalesce repository acquisition and exact PR ref fetches across processes
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7327d4wd92r1n5bnmr1b0zb
hold: null
hold_until: null
created_at: 2026-11-10T15:56:50.319Z
updated_at: 2026-11-10T17:58:29.734Z
started_at: 2026-11-10T15:56:50.858Z
---
Use a keyed cold-acquisition lease outside hierarchy locks, recheck cache after acquisition, and reuse exact PR objects under the current store fetch owner. Preserve restart, cancellation, read-only hits, and different-key concurrency.

## Notes

Implemented source-keyed acquisition leases with durable recheck and inherited Git descriptors, plus exact PR object rechecks under the store fetch lock. Storage and overlay tests passed 189 cases. Cancellation, distinct-source progress, and one-fetch overlap have deterministic coverage.

Draft implementation and deterministic race coverage: https://github.com/jlevy/metabrowser/pull/348 at 53bb1ac97.
