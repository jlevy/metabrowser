---
type: is
id: is-01m2h7hrjfx06hzpr7ptz7k9wn
title: "GitHub Phase 3C: bounded PR index and discovery cache"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
parent_id: is-01m2h3vtmk6apasv27t6ygrrxf
created_at: 2026-09-15T00:30:26.382Z
updated_at: 2026-09-15T01:19:53.402Z
---
Publish a bounded, query-keyed ChangeRequestIndex/v1 after direct PR hydration works. Rows contain only identity, number, URL, title, author, lifecycle/draft, base/head labels, and update time—never review/check summaries or full bundles. Record normalized query identity, stable sort/tie-breaker, per-page provenance, first/last observation times, provider_snapshot/best_effort_window/unknown consistency, dedupe by stable ID, bounds, cursors, and honest collection coverage. Scope pointers/validators by auth context; listing fetches no refs; valid partial may be current with last-complete fallback. Cover continuation, moving remote pages, reauth, stale/offline, missing direct item, and no-ref-fetch.
