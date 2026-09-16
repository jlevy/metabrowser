---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Repository projection: immutable Git-tree source over a shared object store"
kind: feature
status: in_progress
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m0dkj0xzgg9b6kc7ge0fm2ne
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2kw2bht6rte4gtjdq39n1yt
  - type: blocks
    target: is-01m2nzb0geg0hkaapyvj0hdb49
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-19T18:11:56.054Z
updated_at: 2026-09-16T21:11:32.269Z
started_at: 2026-09-16T21:10:44.836Z
---
Implement the repository-owned immutable revision source keyed by RepositoryStoreId and full OID. Enumerate byte-safe trees, modes, symlinks, and submodules; perform bounded blob reads through owned batch Git readers; add leases, cancellation, tree-index bounds, subject lifecycle, and reclamation. Never create a checkout, shared index, local branch, detached worktree, or fake filesystem mtime, watcher, or ignore facts. Share only proven low-level safe-path and lease helpers; archive extraction remains separately owned.
