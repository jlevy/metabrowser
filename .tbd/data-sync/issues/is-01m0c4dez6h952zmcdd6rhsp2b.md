---
type: is
id: is-01m0c4dez6h952zmcdd6rhsp2b
title: "diff/adapters/git.py: the worktree-tied source"
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4dfp54t81297rz61cse4r
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:28:03.932Z
updated_at: 2026-08-19T04:58:37.463Z
closed_at: 2026-08-19T04:58:37.462Z
close_reason: "Landed on claude/diff-core: adapter + oracle against real git trees (5 tests)."
---
class GitDiffSource(DiffSource) over run_git. resolve() runs rev-parse and, for pull requests and branches, merge-base. _raw_changes parses git diff --raw -z -M -C into FileChange records — the -z NUL framing and the newline-before-first-record quirk the history surface documents apply here too. _numstat fills additions/deletions when cheap. file_patch runs a path-limited git diff and reuses the patch-file parser, which is the point of having one format. Merges pass --diff-merges=first-parent, matching the history surface.
