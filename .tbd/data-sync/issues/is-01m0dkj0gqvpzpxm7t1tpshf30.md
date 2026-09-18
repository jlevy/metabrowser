---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Repository projection: immutable Git-tree source over a shared object store"
kind: feature
status: in_progress
priority: 1
version: 60
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2kw2bht6rte4gtjdq39n1yt
  - type: blocks
    target: is-01m2nzb0geg0hkaapyvj0hdb49
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-19T18:11:56.054Z
updated_at: 2026-09-18T10:56:35.655Z
started_at: 2026-09-16T21:10:44.836Z
---
Implement GitRevisionSubject and GitTreeSource over a shared RepositoryStoreTarget and an opaque SourceSession. Define byte-segment GitPath identity and URL/display serialization; enumerate NUL-framed trees with stable byte ordering; read blobs through exclusive actor-style cat-file batch readers that issue info before contents, enforce size gates, drain frames, and poison/restart on cancellation or framing failure. Migrate history, repo discovery, commit detail, refs, diffs, file/raw/container/classification/KPress routes, and built-in sidekicks to exact target plus subject OID semantics. Protect live OIDs with cross-process shared maintenance locks and durable private refs; GC/repack takes the exclusive lock. Add crash/stale-lock recovery, promisor-miss, oversized-blob, invalid-UTF8/newline-name, and two-process/two-OID tests. Never create a checkout, index, branch, worktree, or fake filesystem fact.

## Notes

As-landed through #190 Git include_ignored no-op (0d419179, stacked on #189). include_ignored=0 lists the same tree; SPA hides Show ignored. #189 logical-ext CI still in flight. Next: Git /api/tree depth nesting so SPA depth=2 fetches include grandchildren instead of always children:null. Do not close until review.
