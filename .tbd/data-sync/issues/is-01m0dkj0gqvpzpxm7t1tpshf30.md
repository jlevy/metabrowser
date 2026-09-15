---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Container materialization: bounded transient worktrees and unpacked trees"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0dkj0xzgg9b6kc7ge0fm2ne
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-19T18:11:56.054Z
updated_at: 2026-09-14T23:59:13.011Z
---
Implement only the transient materialization layer described by arch-nav-containers.md: bounded detached worktrees, patch anchors, and archive trees that the ordinary serving path can route into, with safe paths, size/entry bounds, ownership, cancellation, and release-on-close. Do not conflate this with durable repository entries, durable hosted-review snapshots, or recomputable request/browser caches. The repository library owns Git worktrees; archive consumers may reuse the discipline later.
