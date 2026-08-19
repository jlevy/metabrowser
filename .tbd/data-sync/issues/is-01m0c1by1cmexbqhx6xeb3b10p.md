---
type: is
id: is-01m0c1by1cmexbqhx6xeb3b10p
title: "One acquisition workflow: reference clones and transient worktrees in the cache"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T03:34:48.107Z
updated_at: 2026-08-19T03:34:48.107Z
---
Transient repo checkout, transient PR, and PR-on-local-checkout are one workflow varying only in object source and refs: remote URL clones into the purgeable cache; a repo already on disk is borrowed via a reference clone (near-instant, no network); refs are the default branch, refs/pull/<n>/{head,merge}, or arbitrary revisions; when a filesystem tree is needed, a transient detached worktree is materialized inside the cache and purged with it. The user's repository is never fetched into, checked out, or written — preserving the git package's read-only contract. After acquisition every flow converges on the same serve path and comparison context.
