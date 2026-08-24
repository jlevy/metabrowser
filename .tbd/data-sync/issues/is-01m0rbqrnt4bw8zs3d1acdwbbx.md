---
type: is
id: is-01m0rbqrnt4bw8zs3d1acdwbbx
title: Move activity decorations and refresh hints onto the sparse overlay
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqsb3e5ep9c328y6ybk4z
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:54.778Z
updated_at: 2026-08-24T00:48:39.834Z
closed_at: 2026-08-24T00:48:39.820Z
close_reason: Activity discovery now uses bounded CatalogQuery records, refreshes only observed fact mismatches, patches feature-owned overlay fields, preserves PID/quiet behavior and /api/activity, and proves decoration-only changes leave engine, rollup, and catalog identities unchanged.
resolution: null
duplicate_of: null
---
Files: refactor src/metabrowser/active_tracker.py, activity.py, coordinator.py and related active-tracker, activity and SSE tests. Functions: run_active_tracker receives InventoryCoordinator explicitly, reads bounded trackable candidates, updates InventoryOverlay rather than retained filesystem entries, publishes joined host upserts in coordinator order, prunes vanished paths, and submits RefreshRequest only when observed filesystem metadata changed. Preserve quiet-poll smoothing, PID labels, per-tick batching and the /api/activity snapshot. Acceptance: decoration-only changes do not advance engine versions, rollup/catalog totals or filesystem cache keys; browser active badges and labels converge with their current cadence.
