---
type: is
id: is-01m10vgw6vhq82cd495kvhh9gf
title: "GitHub provider Phase 1: browsing model and SoftSchema corpus"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies:
  - type: blocks
    target: is-01m10xd666fefs5z7ft5m58zj0
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-27T05:36:41.690Z
updated_at: 2026-08-28T02:22:49.719Z
---
Before any GitHub API or UI work, define the complete read-only browsing-domain model as closed, versioned SoftSchema contracts and fixtures: provider binding, retrieval, sync manifests, resource sets, tombstones, repository, issues and comments, timeline, pull requests, reviews, review threads and comments, checks, commit statuses, and PullRequestStack. Specify stable IDs, Git object refs, completeness, pagination, provenance, unknown enum handling, tombstones, review anchors, and derived stack evidence. Measure and freeze the immutable-snapshot and atomic-manifest layout. This phase has no network code.
