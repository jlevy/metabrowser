---
type: is
id: is-01kxse0w3xhsyhbksdbn2kt33e
title: "Diff P2: comparison presets, history browsing, and content-at-revision"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0wpvpg9vx64phcr3bh8s
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:59.325Z
updated_at: 2026-08-19T18:12:17.380Z
extensions:
  linear:
    id: fedfa275-330a-4a89-a928-512efc3ff45d
    linked_at: 2026-08-16T08:06:28.528Z
---
Comparison bar: staged, unstaged, all uncommitted, commit, two revisions with resolved endpoints shown. Bounded first-parent log with paging; commit-vs-parent diffs with explicit root/merge policy; side contents at any resolved revision.

## Notes

Includes the adapter gap named in diff-sources-and-anchoring.md path 5: GitDiffSource.resolve currently accepts revisions only; worktree/index snapshots (presets HEAD-vs-worktree, staged, unstaged) need resolve + content resolution for uncommitted sides plus the generation token wiring mb-tcdy consumes.
