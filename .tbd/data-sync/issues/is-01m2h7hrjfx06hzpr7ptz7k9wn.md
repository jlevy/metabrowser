---
type: is
id: is-01m2h7hrjfx06hzpr7ptz7k9wn
title: "GitHub Phase 3C: bounded PR index and discovery cache"
kind: feature
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m2kw2cf1gxnanj6e1wyh6frw
parent_id: is-01m2h3vtmk6apasv27t6ygrrxf
hold: null
hold_until: null
created_at: 2026-09-15T00:30:26.382Z
updated_at: 2026-09-23T00:21:41.197Z
started_at: 2026-09-16T21:10:44.906Z
---
Publish a bounded query-keyed ChangeRequestIndex after direct PR hydration works. Keep rows summary-only and record normalized query identity, deterministic ordering, per-page provenance, observation window and remote consistency, dedupe, bounds, cursors, and honest coverage. Store one repository/auth-scoped index reused by all attached clones and managed URL sources; listing fetches no Git refs. Cover continuation, moving pages, reauth isolation, stale/offline state, missing direct item, and no-ref-fetch.
