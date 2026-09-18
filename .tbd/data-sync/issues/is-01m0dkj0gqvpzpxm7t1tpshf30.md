---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Repository projection: immutable Git-tree source over a shared object store"
kind: feature
status: in_progress
priority: 1
version: 51
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
updated_at: 2026-09-18T09:45:37.595Z
started_at: 2026-09-16T21:10:44.836Z
---
Implement GitRevisionSubject and GitTreeSource over a shared RepositoryStoreTarget and an opaque SourceSession. Define byte-segment GitPath identity and URL/display serialization; enumerate NUL-framed trees with stable byte ordering; read blobs through exclusive actor-style cat-file batch readers that issue info before contents, enforce size gates, drain frames, and poison/restart on cancellation or framing failure. Migrate history, repo discovery, commit detail, refs, diffs, file/raw/container/classification/KPress routes, and built-in sidekicks to exact target plus subject OID semantics. Protect live OIDs with cross-process shared maintenance locks and durable private refs; GC/repack takes the exclusive lock. Add crash/stale-lock recovery, promisor-miss, oversized-blob, invalid-UTF8/newline-name, and two-process/two-OID tests. Never create a checkout, index, branch, worktree, or fake filesystem fact.

## Notes

Twenty-fifth z335 slice: recursive Git directory blob tallies (dir-tallies, stacked on #180 as #181). GitBlobIndex / GitTreeTally from one ls-tree -r plus cat-file info per tree OID. SPA dir nodes and folder envelopes carry total_files / total_size without mtime. A missing blob keeps total_files and omits total_size. Truncation omits the whole tally. Gitlinks are not counted. File Overview stays hidden until dir carries mtime. Treemap still needs a Git-native /api/rollup.

Shipped through this slice: GitPath+tree (#157), lease_revision (#158), shared reader pool (#159), GitLocation collection (#160), file/raw/tree (#161), exclusive gc/repack (#162), diffs (#163), KPress (#164), patch containers (#165), binary chunks (#166), structured parsed (#167), agent-log JSONL (#168), content-key classification (#169), GitDiffSource.content pool (#170), inventory refuse (#171), LFS pointer + promisor miss (#172), /view/ GitPath (#173), SPA tree projection (#174), folder chrome (#175), Markdown/wiki GitPath (#176), folder Overview README (#177), SPA GitPath display chrome (#178), omitted tally chrome (#179), listing blob sizes (#180), recursive dir tallies (this PR).

Still later: inventory open (needs a distinct immutable-tree index), archive containers (mb-380k), serving acquired Git (mb-ew38), Git-native rollup/treemap on a pin (sizes exist; rollup schema still wants mtime and ignore), CLI --show of a Git pin. Do not close until review.
