---
type: is
id: is-01m0c4dfbfnqg3q53y7xzbgc0a
title: "repo_cache.py: reference clones, ref fetching, transient worktrees"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
  - type: blocks
    target: is-01m10vgwqwn8gjdv8fm183vztr
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:28:04.334Z
updated_at: 2026-08-27T05:37:05.712Z
---
ensure_repo(source) -> CacheEntry accepting a URL or a local path; reference_clone(local_path) borrows an on-disk repository with no network; fetch_refs(entry, refspecs) covers refs/pull/<n>/{head,merge} and arbitrary revisions; transient_worktree(entry, revision) materializes a detached worktree inside the cache as a context manager so it is purged on exit. Cloning and fetching live here rather than in git/, keeping that package's read-only contract intact. This is the one acquisition workflow behind all three flows.
