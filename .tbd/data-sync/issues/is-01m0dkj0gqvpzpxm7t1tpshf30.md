---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Repository projection: bounded detached worktrees for immutable revisions"
kind: feature
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m0dkj0xzgg9b6kc7ge0fm2ne
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2kw2bht6rte4gtjdq39n1yt
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-19T18:11:56.054Z
updated_at: 2026-09-16T01:07:30.490Z
---
Implement the repository-owned transient filesystem projection for selected immutable revisions: bounded detached worktrees keyed by cache-entry identity and full OID, safe paths, entry locks, leases, cancellation, root-lifecycle handoff, and reclamation only after owners join. Keep this distinct from durable repository entries, provider snapshots, archive-owned extraction, review-anchor domain records, and recomputable diff/browser caches. Share only proven low-level lease or safe-path helpers.
