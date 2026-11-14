---
type: is
id: is-01m10vgv018nef5svd0kb54gv9
title: "Repository library follow-up: generic Git catalog, refresh, and cache management"
kind: feature
status: open
priority: 2
version: 14
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m10vgvh4pvre1adnkgm2egp1
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-27T05:36:40.448Z
updated_at: 2026-11-14T18:42:01.684Z
started_at: 2026-09-16T21:10:44.853Z
---
Generic Git catalog, refresh, and cache management for the shared repository store, after v0.12. The read-only /api/cache/layout, /api/cache/sources, /api/cache/source, and /api/cache/stores routes already report layout, sources, and stores. Remaining: one catalog over validated source and store records; list, inspect, and Git-only refresh operations; repair diagnostics; recoverable purge; size accounting; attachment visibility; and measured retention, with progress, cancellation, coalescing, and partial-failure reporting. The original design assumed Phase 2B provider jobs and store leases, which the thin-mirror plan superseded or removed (#228); re-plan against the thin-mirror plan before starting (open-repo plan, 'Later: Generic catalog, refresh, and cache management').
