---
type: is
id: is-01m0eb0wvz59swjfh0gbkvjx3t
title: "Git tab: commit selection opens a first-parent comparison"
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-20T01:02:01.070Z
updated_at: 2026-08-20T06:22:02.154Z
closed_at: 2026-08-20T06:22:02.153Z
close_reason: "Landed: /api/plugin/diff/comparison serves a revision's first-parent comparison via GitDiffSource, the diff view accepts a revision ctx, and git_panel mounts that view through the SDK registry. The panel's duplicate file list is gone; it keeps only outside-root files and the bounded-diff statement."
---
The history-view integration seam from the spec's Consumers section: selecting a commit in the Git graph resolves that commit's first-parent comparison (the CLI's --diff REV semantics, via GitDiffSource) and presents it through the container contract — the commit's changed files as container children with change indicators, the change-set summary as the outer view, per-file diff tabs inner, one renderer. No graph-owned diff surface. Presets (HEAD vs worktree, staged, unstaged — mb-8bjd) and branch comparisons are the same wiring with different endpoints. Depends on the container contract (mb-6ba6) and adoption (mb-um0p); serves the graph epic (mb-02na).
