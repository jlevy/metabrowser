---
type: is
id: is-01kxse0vfwwkcq1a6mfdx6v9ad
title: "Diff P1: hardened Git adapter and comparison service (uncommitted view)"
kind: feature
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0w3xhsyhbksdbn2kt33e
  - type: blocks
    target: is-01kxse0vt4cyng7mvtr3hk2rct
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:58.684Z
updated_at: 2026-08-19T04:28:51.298Z
closed_at: 2026-08-19T04:28:51.297Z
close_reason: Superseded by mb-kxvb (adapters/git.py) and mb-uawv (service.py), which split the adapter from the service it registers into.
extensions:
  linear:
    id: 9f2f8636-4e15-42cd-adfd-e7574e92171d
    linked_at: 2026-08-16T08:06:26.279Z
---
Repo discovery incl .git-file worktrees and safe.directory policy; version detection; porcelain v2 status; raw/numstat manifest; per-file semantic patch; cat-file content; untracked synthesis; caps+cancellation; deterministic comparison IDs, generation tokens, bounded LRU, ETags. Routes: POST/GET comparisons, patch, content per plan.
