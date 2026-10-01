---
type: is
id: is-01m2h7jjgpzyfbf10238j32z6q
title: "Hosted review Phase 4B: Pull Requests virtual nav collection"
kind: feature
status: deferred
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies:
  - type: blocks
    target: is-01m2kttf7tse7rs1nwrk9m3jbj
  - type: blocks
    target: is-01m2kw2d2arc9hn25pfsc4me50
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T00:30:52.949Z
updated_at: 2026-10-01T00:13:14.839Z
---
Add the Pull Requests repository-scoped nav panel after direct view and the bounded index. Project only the index row fields—no review/check summary—through RepositoryActivity and reuse bounded paging, virtualization, roving selection, query-key restoration, loading/error, root replacement, and disposal through public SDK. Selection opens the direct PR address; expansion exposes comparison files. Counts/grouping/visibility come from the bounded model. Execute exact panel-window, selection, restoration, replacement, and disposal owners in hosted-review-session and cli-ui-hosted-review.

## Notes

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.
