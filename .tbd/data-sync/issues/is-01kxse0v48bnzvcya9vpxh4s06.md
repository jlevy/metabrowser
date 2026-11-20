---
type: is
id: is-01kxse0v48bnzvcya9vpxh4s06
title: "Diff P0: golden Git fixture repos, adapter contract harness, and baselines"
kind: task
status: closed
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0vfwwkcq1a6mfdx6v9ad
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-07-18T01:38:58.312Z
updated_at: 2026-11-20T19:15:57.500Z
closed_at: 2026-08-19T16:19:41.280Z
close_reason: "Landed: deterministic fixture repos (pinned identity + dates), materialize_tree, and the apply oracle passing against git's own trees — also runnable from the CLI as --diff-check and pinned in the tryscript golden."
extensions: {}
---
Fixture matrix per the plan: modified/added/deleted/renamed/mode-change/binary/untracked/partial-staging/unborn/detached/linked-worktree/non-UTF-8 path/CRLF/no-final-newline plus one pathological generated file. Differential tests vs installed git; record baselines, then set budgets.

## Notes

Scope now includes the apply oracle from the spec: for fixture (base, target) pairs, compute the model, apply through the content resolver, assert tree-hash equality with the target. The fixture script must cover the corner taxonomy: rename+edit above/below similarity thresholds, folder moves, file<->symlink type changes, mode flips, binary transitions, unmerged paths, non-UTF-8 paths, missing trailing newlines.
