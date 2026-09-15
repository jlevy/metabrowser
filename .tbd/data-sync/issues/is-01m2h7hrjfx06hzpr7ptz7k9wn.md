---
type: is
id: is-01m2h7hrjfx06hzpr7ptz7k9wn
title: "GitHub Phase 3C: bounded PR index and discovery cache"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
parent_id: is-01m2h3vtmk6apasv27t6ygrrxf
created_at: 2026-09-15T00:30:26.382Z
updated_at: 2026-09-15T00:30:52.949Z
---
Publish a bounded, paginated ChangeRequestIndex/v1 after direct PR hydration works. Store only provider-neutral summaries plus query identity, page cursors, item/page bounds, completeness, freshness, validators, and rate-limit outcomes. Listing fetches no PR Git refs or full bundles; a failed/partial refresh leaves the previous current index readable and exposes the new outcome separately. Add continuation, stale/offline, missing direct item, and no-ref-fetch goldens.
