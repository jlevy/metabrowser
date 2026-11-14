---
type: is
id: is-01kxse0w3xhsyhbksdbn2kt33e
title: "Diff: comparison presets, two-revision comparisons, and content at a revision in a served folder"
kind: feature
status: open
priority: 2
version: 11
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
updated_at: 2026-11-14T18:43:22.703Z
extensions:
  linear:
    id: fedfa275-330a-4a89-a928-512efc3ff45d
    linked_at: 2026-08-16T08:06:28.528Z
---
Remaining: a comparison chooser with an all-uncommitted (HEAD to worktree) preset; an explicit two-revision comparison with its resolved endpoints shown (its address is mb-hgus's /compare/ route); and reading a file at a revision in a served folder, which has no such route today (View file, #248, works only on a pinned revision). On main already: Commits-tab history with paging; commit-versus-first-parent comparisons with the empty tree for a root commit and --diff-merges=first-parent (diff/adapters/git.py). Staged, unstaged, and unmerged comparisons belong to the Git-status plan (mb-u4mf, mb-vibn); the parser reports combined 'diff --cc' output as unsupported.

## Notes

Unmerged (U) end-to-end belongs here too: a commit-pair adapter can never produce U — conflicts live in the index — so unmerged support arrives with the index/worktree snapshot work. The parser now surfaces combined ('diff --cc') conflict output as unsupported rather than misparsing it.
