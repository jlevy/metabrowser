---
type: is
id: is-01kzp8494h42vn4hqeps21sw68
title: Decide whether Live earns a recency segment
kind: task
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:39.856Z
updated_at: 2026-08-10T18:08:16.906Z
closed_at: 2026-08-10T18:08:16.902Z
close_reason: "Decided: keep Live as-is. It is the active tracker's ~30s window and the only recency value that updates over SSE without a refetch; the always-empty-on-a-quiet-repo downside is accepted for now."
---
Live is the active tracker's ~30s window (stale_after_s=30 plus up to 30s quiet-poll hysteresis), not an hour, and it is the only recency value that updates over SSE without a refetch. Against: on a quiet repo it is always empty, which reads as broken. Options are keep, relabel to 30s for a uniform axis, or drop. See Open Questions in the spec.
