---
type: is
id: is-01m732t9rgn9xnfxfzejj9psqp
title: Coalesce repository acquisition and exact PR ref fetches across processes
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7327d4wd92r1n5bnmr1b0zb
hold: null
hold_until: null
created_at: 2026-11-10T15:56:50.319Z
updated_at: 2026-11-10T15:56:50.858Z
started_at: 2026-11-10T15:56:50.858Z
---
Use a keyed cold-acquisition lease outside hierarchy locks, recheck cache after acquisition, and reuse exact PR objects under the current store fetch owner. Preserve restart, cancellation, read-only hits, and different-key concurrency.
