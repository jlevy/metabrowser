---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Repository projection: immutable Git-tree source over a shared object store"
kind: feature
status: in_progress
priority: 1
version: 73
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
updated_at: 2026-09-18T15:28:45.047Z
started_at: 2026-09-16T21:10:44.836Z
---
Implement GitRevisionSubject and GitTreeSource over a shared RepositoryStoreTarget and an opaque SourceSession. Define byte-segment GitPath identity and URL/display serialization; enumerate NUL-framed trees with stable byte ordering; read blobs through exclusive actor-style cat-file batch readers that issue info before contents, enforce size gates, drain frames, and poison/restart on cancellation or framing failure. Migrate history, repo discovery, commit detail, refs, diffs, file/raw/container/classification/KPress routes, and built-in sidekicks to exact target plus subject OID semantics. Protect live OIDs with cross-process shared maintenance locks and durable private refs; GC/repack takes the exclusive lock. Add crash/stale-lock recovery, promisor-miss, oversized-blob, invalid-UTF8/newline-name, and two-process/two-OID tests. Never create a checkout, index, branch, worktree, or fake filesystem fact.

## Notes

Collapsed #157–#199 into 7 stacked review drafts on #156 (source-boundary). Odd-names is committed at db141a57 on the chrome tip. #199 was 7-green on 8850fea9 before the collapse.

New review layers (created by a sibling agent; do not recreate):
1. https://github.com/jlevy/metabrowser/pull/200 — cursor/v011-git-revision-source-bd04 @ 69b81956, base #156; supersedes #157–#162
2. https://github.com/jlevy/metabrowser/pull/201 — cursor/v011-git-revision-content-bd04 @ 0203b174, base source; supersedes #163–#170
3. https://github.com/jlevy/metabrowser/pull/203 — cursor/v011-git-revision-view-bd04 @ 19ebc64a, base content; supersedes #171–#173
4. https://github.com/jlevy/metabrowser/pull/202 — cursor/v011-git-revision-spa-bd04 @ 039b641b, base view; supersedes #174–#178
5. https://github.com/jlevy/metabrowser/pull/206 — cursor/v011-git-revision-index-bd04 @ c7d5c05b, base spa; supersedes #179–#184
6. https://github.com/jlevy/metabrowser/pull/204 — cursor/v011-git-revision-filters-bd04 @ 317bdd1f, base index; supersedes #185–#192
7. https://github.com/jlevy/metabrowser/pull/205 — cursor/v011-git-revision-chrome-bd04 @ db141a57, base filters; supersedes #193–#199 plus odd-names

This VM cannot create or close PRs with gh: GH_TOKEN and GITHUB_TOKEN are unset (Cloud secrets are not injected into an already-running agent). gh is logged in as cursor[bot] and can read, but create/close/comment return "Resource not accessible by integration". #157–#199 are still open and need close from a session with write access. Do not merge. Do not close #156.

Out of scope still: inventory coordinator open, archive containers (mb-380k), serving acquired Git (mb-ew38), CLI --show of a Git pin. Do not close mb-z335. Do not start mb-oueh / mb-ew38 / mb-d658 / mb-380k.
