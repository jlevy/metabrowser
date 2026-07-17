---
type: is
id: is-01kxry1sswh4hv52jgwefmm8a3
title: "Review D4: research doc git-adapter safety gaps: core.fsmonitor, hooksPath, safe.directory, git version gates, worktree .git file"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T20:59:52.508Z
updated_at: 2026-07-17T21:04:55.522Z
closed_at: 2026-07-17T21:04:55.522Z
close_reason: "Addressed in commit cc92da0 on the diff-research branch: platform prerequisites section + Phase 0 fold-in, packaging-reality paragraph, self-describing comparison IDs, git adapter safety additions, tool-surface and tree-decoration open decisions, docs-tree conventions in development.md. make verify green (705 tests)."
---
git status can execute repo-configured fsmonitor; safe.directory ownership failures need policy; cat-file --batch-command -Z needs modern git (feature-detect); worktree checkouts have .git as file.
