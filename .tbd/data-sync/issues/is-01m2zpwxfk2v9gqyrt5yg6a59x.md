---
type: is
id: is-01m2zpwxfk2v9gqyrt5yg6a59x
title: "S216-10: add a multi-entry Git-pin golden, real browser source-kind tests, and an algorithmic R5 regression test"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - stack:pr216
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T15:28:02.544Z
updated_at: 2026-09-23T00:23:26.596Z
---
Finding S216-10 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-10.

## Notes

Started then cancelled by the user on 2026-09-21. Partial work is in the worktree .claude/worktrees/agent-afc86361706a59e8e on branch test/git-pin-golden (3 dirty files, nothing committed): a deterministic multi-entry origin fixture and a generated transcript, stopped while inspecting the generated error blocks. Nothing reached the stack. Anyone resuming should merge origin/cursor/v011-git-revision-pin-bd04 first, then regenerate rather than hand-edit. Still open: the pin's only golden is a one-file origin whose /api/tree?depth=0 has empty entries and tree, so it pins almost no data semantics, against the AGENTS.md nontrivial-golden rule.
