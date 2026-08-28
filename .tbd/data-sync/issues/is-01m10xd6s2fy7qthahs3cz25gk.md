---
type: is
id: is-01m10xd6s2fy7qthahs3cz25gk
title: "GitHub provider Phase 4: stacked PRs and cross-object projections"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T06:09:38.593Z
updated_at: 2026-08-28T02:22:50.755Z
---
Implement PullRequestStack derivation over validated GitHub and Git snapshots with explicit evidence, algorithm version, conflicts, cycles, missing members, and input snapshot IDs. Add adapters for explicit tool metadata without hard-coding them into core, then add stack navigation and aggregate status. Recompute projections without mutating source PR records.
