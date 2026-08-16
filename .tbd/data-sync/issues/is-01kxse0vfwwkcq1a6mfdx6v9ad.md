---
type: is
id: is-01kxse0vfwwkcq1a6mfdx6v9ad
title: "Diff P1: hardened Git adapter and comparison service (uncommitted view)"
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-18-git-diff-view.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0w3xhsyhbksdbn2kt33e
  - type: blocks
    target: is-01kxse0vt4cyng7mvtr3hk2rct
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:58.684Z
updated_at: 2026-08-16T08:05:43.230Z
extensions:
  linear:
    id: 9f2f8636-4e15-42cd-adfd-e7574e92171d
    linked_at: 2026-08-16T08:05:43.230Z
---
Repo discovery incl .git-file worktrees and safe.directory policy; version detection; porcelain v2 status; raw/numstat manifest; per-file semantic patch; cat-file content; untracked synthesis; caps+cancellation; deterministic comparison IDs, generation tokens, bounded LRU, ETags. Routes: POST/GET comparisons, patch, content per plan.
