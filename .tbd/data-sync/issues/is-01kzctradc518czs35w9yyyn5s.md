---
type: is
id: is-01kzctradc518czs35w9yyyn5s
title: "git: bounded async git execution and repo discovery"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctrefhe1tktd7wp3fvj3xg
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:42:46.571Z
updated_at: 2026-08-07T01:29:02.962Z
closed_at: 2026-08-07T01:29:02.961Z
close_reason: null
---
Add metabrowser/git/exec.py (asyncio.create_subprocess_exec, fixed argv, timeout, stdout byte cap, typed errors, no stderr passthrough) and metabrowser/git/repo.py (repo root discovery reusing tree.py, HEAD/detached state, git executable capability, TTL-cached GitRepoInfo). Add the new bounded constants to settings.py.
