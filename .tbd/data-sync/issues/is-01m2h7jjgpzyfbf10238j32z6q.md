---
type: is
id: is-01m2h7jjgpzyfbf10238j32z6q
title: "Hosted review Phase 4B: Pull Requests virtual nav collection"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-09-15T00:30:52.949Z
updated_at: 2026-09-15T01:19:56.145Z
---
Add the Pull Requests repository-scoped nav panel after direct view and the bounded index. Project only the index row fields—no review/check summary—through RepositoryActivity and reuse bounded paging, virtualization, roving selection, query-key restoration, loading/error, root replacement, and disposal through public SDK. Selection opens the direct PR address; expansion exposes comparison files. Counts/grouping/visibility come from the bounded model. Execute exact panel-window, selection, restoration, replacement, and disposal owners in hosted-review-session and cli-ui-hosted-review.
