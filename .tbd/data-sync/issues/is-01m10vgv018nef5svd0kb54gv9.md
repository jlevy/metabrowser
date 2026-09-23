---
type: is
id: is-01m10vgv018nef5svd0kb54gv9
title: "Repository library Phase 2: generic Git catalog, refresh, and cache management"
kind: feature
status: in_progress
priority: 2
version: 12
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m10vgvh4pvre1adnkgm2egp1
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-27T05:36:40.448Z
updated_at: 2026-09-23T00:40:30.959Z
started_at: 2026-09-16T21:10:44.853Z
---
Complete the generic source/store catalog, refresh, and cache-management phase after the provider-facing v0.11 subset. Scan validated source aliases and repository-store state; add list, inspect, Git-only refresh, repair diagnostics, recoverable alias/store purge, size accounting, attachment visibility, and measured retention. Publish verified Metabrowser-owned refs without changing live subjects, preserve objects reachable from any alias, provider, or lease, and report progress, cancellation, coalescing, and partial failure. Provider refresh remains separate.
