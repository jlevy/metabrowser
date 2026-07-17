---
type: is
id: is-01kxry1sswh4hv52jgwefmm8a3
title: "Review D4: research doc git-adapter safety gaps: core.fsmonitor, hooksPath, safe.directory, git version gates, worktree .git file"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T20:59:52.508Z
updated_at: 2026-07-17T20:59:52.508Z
---
git status can execute repo-configured fsmonitor; safe.directory ownership failures need policy; cat-file --batch-command -Z needs modern git (feature-detect); worktree checkouts have .git as file.
