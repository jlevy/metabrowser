---
type: is
id: is-01m2zpwxfk2v9gqyrt5yg6a59x
title: "S216-10: add a multi-entry Git-pin golden, real browser source-kind tests, and an algorithmic R5 regression test"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10
labels:
  - stack:pr216
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m35tapm6wjnn235hr3s669b7
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
hold: null
hold_until: null
created_at: 2026-09-20T15:28:02.544Z
updated_at: 2026-09-23T05:32:21.245Z
started_at: 2026-09-23T03:31:07.190Z
closed_at: 2026-09-23T05:32:21.244Z
close_reason: "Done on codex/v012-foundation-stabilization (PR #226) (efede255, 8e1a9bef, 8edc67a3). Multi-entry fast-import pin golden (cli-git-pin.txt) covering nested dirs, JSON/JSONL, PNG, binary, oversize (windowed and 416), symlink, executable, gitlink, and newline/tab/non-UTF-8 names. Operation-count regressions in test_git_pin_scaling.py fail when R5, the memo or the node budget is reverted. A source-kind session (tests/dom/source-kind-session.js, cli-ui-source-kind.tryscript.md, parity row navigation.served-source-kind) replays production app.js over fixtures recorded from the live server. No genuine real-browser test is possible until Phase 2A serves pins over HTTP. Finding while doing this: pin tree order differed from folders; fixed in 9845030c (directories first)."
resolution: null
duplicate_of: null
---
Finding S216-10 from the v0.11 stabilization review. Owning layer: PR #216. Full evidence, path:line, and suggested fix are in the notes of mb-gacf under S216-10.

## Notes

Started then cancelled by the user on 2026-09-21. Partial work is in the worktree .claude/worktrees/agent-afc86361706a59e8e on branch test/git-pin-golden (3 dirty files, nothing committed): a deterministic multi-entry origin fixture and a generated transcript, stopped while inspecting the generated error blocks. Nothing reached the stack. Anyone resuming should merge origin/cursor/v011-git-revision-pin-bd04 first, then regenerate rather than hand-edit. Still open: the pin's only golden is a one-file origin whose /api/tree?depth=0 has empty entries and tree, so it pins almost no data semantics, against the AGENTS.md nontrivial-golden rule.
