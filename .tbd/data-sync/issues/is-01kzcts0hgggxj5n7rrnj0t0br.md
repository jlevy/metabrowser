---
type: is
id: is-01kzcts0hgggxj5n7rrnj0t0br
title: "git: server-side tests over fixture repositories"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctt14e1nb4k36bc6jy2qe1
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:43:09.231Z
updated_at: 2026-08-07T01:29:03.006Z
closed_at: 2026-08-07T01:29:03.006Z
close_reason: null
---
Build real repositories with git in tmp_path and cover: linear history, a merge, an octopus merge, a rename, a binary change, a detached HEAD, a served root below the repo root, an empty repository, a non-repository root, and a missing git executable. Run every emitted shape through the wire validators, and assert the documented response for timeouts, oversized output, a bad revision, and out-of-range limit.
