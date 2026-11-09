---
type: is
id: is-01kxse0w3xhsyhbksdbn2kt33e
title: "Diff P2: comparison presets, history browsing, and content-at-revision"
kind: feature
status: open
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0wpvpg9vx64phcr3bh8s
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
child_order_hints:
  - is-01m715sfem46c801k52wr03qt6
  - is-01m718rgbk80mnnjb8d4b1r4xz
created_at: 2026-07-18T01:38:59.325Z
updated_at: 2026-11-09T23:02:14.117Z
extensions:
  linear:
    id: fedfa275-330a-4a89-a928-512efc3ff45d
    linked_at: 2026-08-16T08:06:28.528Z
---
Comparison bar: staged, unstaged, all uncommitted, commit, two revisions with resolved endpoints shown. Bounded first-parent log with paging; commit-vs-parent diffs with explicit root/merge policy; side contents at any resolved revision.

## Notes

Unmerged (U) end-to-end belongs here too: a commit-pair adapter can never produce U — conflicts live in the index — so unmerged support arrives with the index/worktree snapshot work. The parser now surfaces combined ('diff --cc') conflict output as unsupported rather than misparsing it.
