---
type: is
id: is-01m7v6edc1nqgwd7ef1r7tt0zb
title: Show pushed (compressed) size of commits and pull requests, with uncompressed diff size
kind: feature
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/627
    at: 2026-11-20T17:02:07.272Z
delegate: claude-code@vm
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T00:42:01.473Z
updated_at: 2026-11-20T18:01:58.762Z
started_at: 2026-11-20T00:42:04.553Z
closed_at: 2026-11-20T04:48:00.270Z
close_reason: "Implemented in jlevy/metabrowser#627: commit and pull request sizes as Git pushes them, kept beside the store, shown on a size line above the Diff summary."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: c1e6908b-4758-492e-abde-167466de3b27
    linked_at: 2026-11-20T18:01:58.758Z
---
Each commit and each pull request shows its size as Git pushes it: the bytes of a thin pack of head ^base (base = first parent for a commit, merge base for a pull request), with git's delta search pinned so the number is a function of the two commit IDs. A tooltip gives the uncompressed diff size (bytes of git diff --binary). Commit IDs are immutable, so a measured size is never recomputed: kept in memory, and for a repository store in a bank beside the store. Research measurements: thin pack 5-70 ms per change on this repository; sum of new objects and objectsize:disk are misleading.
