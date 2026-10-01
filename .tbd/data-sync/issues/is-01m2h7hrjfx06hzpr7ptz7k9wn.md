---
type: is
id: is-01m2h7hrjfx06hzpr7ptz7k9wn
title: "GitHub Phase 3C: bounded PR index and discovery cache"
kind: feature
status: deferred
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m2kw2cf1gxnanj6e1wyh6frw
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-15T00:30:26.382Z
updated_at: 2026-10-01T00:13:14.029Z
started_at: 2026-09-16T21:10:44.906Z
---
Publish a bounded query-keyed ChangeRequestIndex after direct PR hydration works. Keep rows summary-only and record normalized query identity, deterministic ordering, per-page provenance, observation window and remote consistency, dedupe, bounds, cursors, and honest coverage. Store one repository/auth-scoped index reused by all attached clones and managed URL sources; listing fetches no Git refs. Cover continuation, moving pages, reauth isolation, stale/offline state, missing direct item, and no-ref-fetch.

## Notes

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.
