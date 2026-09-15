---
type: is
id: is-01m10vgv018nef5svd0kb54gv9
title: "Repository library Phase 2: generic Git catalog, refresh, and cache management"
kind: feature
status: open
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01m10vgvh4pvre1adnkgm2egp1
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T05:36:40.448Z
updated_at: 2026-09-14T23:27:51.033Z
---
Complete the generic repository catalog, refresh, and cache-management phase after the provider-facing v0.11 subset in mb-jlon. Scan validated repository.yml and state.yml pairs into a provider-neutral catalog; add list, inspect, Git-only refresh, repair diagnostics, recoverable purge, size accounting, and measured retention policy; fetch refs without mutating active gitroot; stage promotion outside live sessions; and report progress, cancellation, and partial failure. Provider refresh remains separate.
