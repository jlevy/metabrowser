---
type: is
id: is-01m10vgv018nef5svd0kb54gv9
title: "Repository library Phase 2: generic Git catalog, refresh, and cache management"
kind: feature
status: open
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01m10vgvh4pvre1adnkgm2egp1
  - type: blocks
    target: is-01m10xd666fefs5z7ft5m58zj0
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T05:36:40.448Z
updated_at: 2026-08-27T06:09:56.553Z
---
Scan validated repository.yml and state.yml pairs into a provider-neutral catalog. Add list, inspect, Git-only refresh, repair diagnostics, and recoverable purge; fetch refs without mutating active gitroot; stage promotion outside live sessions; report progress, cancellation, and partial failure; measure size before eviction. Provider refresh does not enter this phase.
