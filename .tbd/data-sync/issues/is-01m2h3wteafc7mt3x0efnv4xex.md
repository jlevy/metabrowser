---
type: is
id: is-01m2h3wteafc7mt3x0efnv4xex
title: "Hosted review Phase 5: issue and timeline model, cache, and views"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-14T23:26:34.435Z
updated_at: 2026-09-14T23:50:52.254Z
---
Extend the provider-neutral hosted-review registry with Issue, IssueComment, and TimelineEvent contracts, bounded indexes and selected bundles, and plugin-owned issue views, with GitHub as the first adapter. Decide whether the primary issue artifact uses SoftSchema frontmatter-md from the consumed-values/body split. Reuse snapshot, completeness, freshness, pagination, rate-limit, auth, and untrusted-content contracts. This remains outside v0.11.
