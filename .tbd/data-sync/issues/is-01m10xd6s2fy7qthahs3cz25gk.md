---
type: is
id: is-01m10xd6s2fy7qthahs3cz25gk
title: "Hosted review Phase 6: stacked change requests and projections"
kind: feature
status: deferred
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T06:09:38.593Z
updated_at: 2026-10-01T00:13:23.993Z
---
Implement ChangeRequestStack derivation over provider-neutral hosted-review and Git snapshots with explicit evidence, algorithm version, conflicts, cycles, missing members, and input snapshot IDs. Add adapters for explicit provider or tool metadata without hard-coding them into core, then add stack navigation and aggregate status. Recompute projections without mutating source change-request records.

## Notes

2026-09-30: deferred; this later work assumes the provider store retired by the thin-mirror plan. Re-plan before starting.
