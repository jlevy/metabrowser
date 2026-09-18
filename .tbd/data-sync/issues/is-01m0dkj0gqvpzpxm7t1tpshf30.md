---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Repository projection: immutable Git-tree source over a shared object store"
kind: feature
status: in_progress
priority: 1
version: 76
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
updated_at: 2026-09-18T18:32:39.125Z
started_at: 2026-09-16T21:10:44.836Z
---
Implement GitRevisionSubject and GitTreeSource over a shared RepositoryStoreTarget and an opaque SourceSession. Define byte-segment GitPath identity and URL/display serialization; enumerate NUL-framed trees with stable byte ordering; read blobs through exclusive actor-style cat-file batch readers that issue info before contents, enforce size gates, drain frames, and poison/restart on cancellation or framing failure. Migrate history, repo discovery, commit detail, refs, diffs, file/raw/container/classification/KPress routes, and built-in sidekicks to exact target plus subject OID semantics. Protect live OIDs with cross-process shared maintenance locks and durable private refs; GC/repack takes the exclusive lock. Add crash/stale-lock recovery, promisor-miss, oversized-blob, invalid-UTF8/newline-name, and two-process/two-OID tests. Never create a checkout, index, branch, worktree, or fake filesystem fact.

## Notes

Collapsed again from 7 review drafts (#200–#206) into 3 phase layers on #156. Layer sizes are `git diff --shortstat BASE...HEAD` on each PR’s own base (not vs main). Do not recreate the seven layers or the #157–#199 slices.

Measured #200–#206 layers: 3035 / 2109 / 505 / 699 / 1498 / 778 / 1084. Combined vs #156: 79 files, +8434/−500.

Phase branches pushed at existing tip SHAs (no new commits):
1. cursor/v011-git-revision-source-content-bd04 @ 0203b174 — source+content (#200+#201), 42 files +4749/−333, base #156
2. cursor/v011-git-revision-view-spa-bd04 @ 039b641b — view+SPA (#203+#202), 29 files +1087/−89, base phase 1
3. cursor/v011-git-revision-index-chrome-bd04 @ db141a57 — index+filters+chrome (#206+#204+#205), 44 files +2875/−355, base phase 2

gh pr create failed: GraphQL Resource not accessible by integration (cursor[bot] lacks pull_requests=write). ManagePullRequest is not available in this subagent session. Draft PRs were not opened; #200–#206 were not closed. Do not merge. Do not close #156.

Out of scope still: inventory coordinator open, archive containers (mb-380k), serving acquired Git (mb-ew38), CLI --show of a Git pin. Do not close mb-z335. Do not start mb-oueh / mb-ew38 / mb-d658 / mb-380k.
