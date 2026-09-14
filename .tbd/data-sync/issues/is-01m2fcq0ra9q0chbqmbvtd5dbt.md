---
type: is
id: is-01m2fcq0ra9q0chbqmbvtd5dbt
title: "PR #117 review R1: gitignore test git init writes core.bare=true into the real repository under a linked-worktree pre-push hook"
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m2fcq020gq0zzxgs62nrz5rp
created_at: 2026-09-14T07:22:12.617Z
updated_at: 2026-09-14T07:22:25.366Z
---
tests/test_gitignore_hierarchical.py:118 (_git_verdicts) and :143 (git init) inherit GIT_DIR from a linked-worktree pre-push hook, so git init rewrites the shared .git/config with core.bare=true. Confirmed live. Fix: scrub metabrowser.git.process._REPO_PINNING_GIT_VARS once in tests/conftest.py and in both calls; hook-environment regression test against a decoy repository; audit tests/, devtools/, tests/golden/*.tryscript.md. PR #117.
