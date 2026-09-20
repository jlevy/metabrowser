---
type: is
id: is-01m0c4dfbfnqg3q53y7xzbgc0a
title: "repo_cache.py: reference clones, ref fetching, transient worktrees"
kind: feature
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:28:04.334Z
updated_at: 2026-09-20T16:45:01.978Z
closed_at: 2026-09-14T23:27:56.646Z
close_reason: "Superseded during the v0.11 plan reconciliation: generic clone/acquisition is owned by mb-h51g and provider job/ref fetching by mb-jlon; GitHub PR caching and presentation are owned by mb-duu7, mb-wx32, and mb-r19i. The general diff plan retains only the source-neutral Git/File Diff Format renderer boundary."
resolution: null
duplicate_of: null
---
ensure_repo(source) -> CacheEntry accepting a URL or a local path; reference_clone(local_path) borrows an on-disk repository with no network; fetch_refs(entry, refspecs) covers refs/pull/<n>/{head,merge} and arbitrary revisions; transient_worktree(entry, revision) materializes a detached worktree inside the cache as a context manager so it is purged on exit. Cloning and fetching live here rather than in git/, keeping that package's read-only contract intact. This is the one acquisition workflow behind all three flows.
