---
type: is
id: is-01m0vscnvzcjatq9nd43zvqnwa
title: Design and implement scalable Git history continuation
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
labels:
  - release:v0.9.0
dependencies:
  - type: blocks
    target: is-01m0vsd8dnak6hw2b87x5awch6
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:23:14.801Z
updated_at: 2026-08-26T23:52:50.446Z
---
Implement the measured server-side history session: resolve one ref scope, stream one ordered Git walk, spool framed pages for bounded-memory replay, and replace offset cursors with opaque session/page tokens and a scope fingerprint. Bound parser reads, sessions, subprocesses, idle lifetime, and cleanup; distinguish malformed, stale, expired, and Git failures; test exact order across branches and merges, page replay, moved refs, empty history, and deep continuation without git log --skip.
