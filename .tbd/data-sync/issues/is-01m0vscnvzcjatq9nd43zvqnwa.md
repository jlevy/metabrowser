---
type: is
id: is-01m0vscnvzcjatq9nd43zvqnwa
title: Design and implement scalable Git history continuation
kind: task
status: closed
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
labels:
  - release:v0.9.0
dependencies:
  - type: blocks
    target: is-01m0vsd8dnak6hw2b87x5awch6
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:23:14.801Z
updated_at: 2026-08-27T04:37:26.236Z
closed_at: 2026-08-27T04:37:26.235Z
close_reason: "Implemented measured replayable Git history sessions with exact ordering, bounded lifecycle and storage, explicit recovery errors, and complete failure cleanup; commit 5b3173b passed make verify, pre-push, and all five PR #86 checks."
resolution: null
duplicate_of: null
---
Implement the measured server-side history session: resolve one ref scope, stream one ordered Git walk, spool framed pages for bounded-memory replay, and replace offset cursors with opaque session/page tokens and a scope fingerprint. Bound parser reads, sessions, subprocesses, idle lifetime, and cleanup; distinguish malformed, stale, expired, and Git failures; test exact order across branches and merges, page replay, moved refs, empty history, and deep continuation without git log --skip.

## Notes

Started after mb-t875 completed and PR #86 exact checkpoint 04fc42a passed all five GitHub checks. Implement server continuation test-first against the accepted one-walk framed replay design and frozen settings budgets; keep the browser on the released cursor until the coordinated Phase 4 integration commit.
