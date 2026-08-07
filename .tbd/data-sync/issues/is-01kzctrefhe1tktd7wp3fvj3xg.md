---
type: is
id: is-01kzctrefhe1tktd7wp3fvj3xg
title: "git: wire models and runtime validators"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctrj7w66vc2phrc40syqfd
  - type: blocks
    target: is-01kzctrph2jcrdp5v7f91ga2a6
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-07T00:42:50.736Z
updated_at: 2026-08-07T00:42:58.977Z
---
Add metabrowser/git/wire.py: GitRef, GitAuthor, GitCommit, GitLogPage, GitFileChange, GitCommitStats, GitCommitDetail, and GitRepoInfo TypedDicts plus validate_git_commit / validate_git_log_page / validate_git_commit_detail, following the wire_models.py convention and its required-key gate sets.
