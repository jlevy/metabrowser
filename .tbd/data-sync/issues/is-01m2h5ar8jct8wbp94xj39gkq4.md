---
type: is
id: is-01m2h5ar8jct8wbp94xj39gkq4
title: "Hosted review follow-up: GitLab provider adapter"
kind: feature
status: deferred
priority: 2
version: 3
spec_path: docs/project/architecture/arch-hosted-review-model.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-14T23:51:39.523Z
updated_at: 2026-10-01T00:13:25.251Z
---
Implement a future GitLab provider adapter against the shipped provider-neutral hosted-review port and contracts. Map merge requests, reviews/discussions, pipelines/statuses, repository identity, pagination, freshness, auth, and selected Git refs without adding provider branches to common views or opaque extension mappings. Add only GitLab-specific companion records with named consumers when a GitLab concept has no honest common meaning. This is outside v0.11 and exists to keep the second named provider consumer tracked rather than speculative in the first format.

## Notes

2026-09-30: deferred; this later work assumes the provider store retired by the thin-mirror plan. Re-plan before starting.
