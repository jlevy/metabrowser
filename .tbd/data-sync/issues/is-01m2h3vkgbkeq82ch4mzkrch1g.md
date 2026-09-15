---
type: is
id: is-01m2h3vkgbkeq82ch4mzkrch1g
title: "Repository cache Phase 3 foundation: provider jobs and selected refs"
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h3vtmk6apasv27t6ygrrxf
  - type: blocks
    target: is-01m10xd666fefs5z7ft5m58zj0
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-14T23:25:54.570Z
updated_at: 2026-09-14T23:50:51.006Z
---
Extract the provider-facing subset of generic cache management needed for the v0.11 GitHub vertical slice: per-entry job progress, cancellation and stage outcomes; provider namespace allocation; and bounded core-side fetch/prune of explicitly selected refs into a Metabrowser-owned namespace. Preserve the pinned active gitroot, use application-home locking and the existing Git process boundary, expose logical state through registered read routes, and keep provider schemas, gh transport, auth, and refresh policy out of core. Full catalog, chooser, purge, eviction, and generic refresh remain in mb-0ybg and mb-vmzy.
