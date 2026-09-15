---
type: is
id: is-01m2h3vkgbkeq82ch4mzkrch1g
title: "Repository cache Phase 3 foundation: provider jobs and selected refs"
kind: task
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h3vtmk6apasv27t6ygrrxf
  - type: blocks
    target: is-01m10xd666fefs5z7ft5m58zj0
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-14T23:25:54.570Z
updated_at: 2026-09-15T01:19:47.946Z
---
Extract the provider-facing generic job foundation: per-entry progress, cancellation and stage outcomes; provider namespace allocation; and jobs.py-owned fetch_selected_ref/request_ref_fetch for bounded fetch/prune of one explicit ref into a Metabrowser namespace. selection.py performs no network work. Preserve pinned gitroot, stage network results with no lock held, then revalidate under the documented entry lock order; expose logical state through registered routes. Keep provider schemas, gh, auth, refresh policy, catalog, chooser, purge, and eviction out of core.
