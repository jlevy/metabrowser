---
type: is
id: is-01m2h3vkgbkeq82ch4mzkrch1g
title: "Repository cache Phase 3 foundation: provider jobs and selected refs"
kind: task
status: in_progress
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
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
    target: is-01m2p38vk3d6gkv2ts21bzfzw3
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-14T23:25:54.570Z
updated_at: 2026-09-16T21:52:49.628Z
started_at: 2026-09-16T21:10:44.862Z
---
Extract provider-facing generic jobs over shared repository stores: per-store progress, coalescing, cancellation and stage outcomes; jobs.py-owned fetch_selected_ref and request_ref_fetch for bounded fetch of explicit refs into a Metabrowser namespace; and full-OID verification before ref publication. selection.py performs no network work. Hold no lock during network; publish under repository-store locking; never mutate an attached checkout, create a worktree, or expose store paths. Keep provider schemas, gh, auth, catalog, chooser, and eviction out of core.
