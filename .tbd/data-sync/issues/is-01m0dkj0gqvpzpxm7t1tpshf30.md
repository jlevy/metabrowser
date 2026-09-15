---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Container materialization: bounded transient worktrees and unpacked trees"
kind: feature
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m0dkj0xzgg9b6kc7ge0fm2ne
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-19T18:11:56.054Z
updated_at: 2026-09-15T00:39:21.843Z
---
Implement the reusable transient materialization primitive in arch-nav-containers.md, with selected repository revisions as the first v0.11 consumer: bounded detached worktrees keyed by entry identity and immutable OID, safe paths, size/entry bounds, leases, cancellation, root-lifecycle handoff, and release/reclamation after all owners join. Keep this distinct from durable repository entries, durable hosted-review snapshots, and recomputable request/browser caches; later patch-anchor and archive consumers may reuse the same discipline.
