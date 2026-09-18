---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Repository projection: immutable Git-tree source over a shared object store"
kind: feature
status: in_progress
priority: 1
version: 72
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
updated_at: 2026-09-18T15:28:00.093Z
started_at: 2026-09-16T21:10:44.836Z
---
Implement GitRevisionSubject and GitTreeSource over a shared RepositoryStoreTarget and an opaque SourceSession. Define byte-segment GitPath identity and URL/display serialization; enumerate NUL-framed trees with stable byte ordering; read blobs through exclusive actor-style cat-file batch readers that issue info before contents, enforce size gates, drain frames, and poison/restart on cancellation or framing failure. Migrate history, repo discovery, commit detail, refs, diffs, file/raw/container/classification/KPress routes, and built-in sidekicks to exact target plus subject OID semantics. Protect live OIDs with cross-process shared maintenance locks and durable private refs; GC/repack takes the exclusive lock. Add crash/stale-lock recovery, promisor-miss, oversized-blob, invalid-UTF8/newline-name, and two-process/two-OID tests. Never create a checkout, index, branch, worktree, or fake filesystem fact.

## Notes

Collapsed #157–#199 into 7 stacked review branches on #156 (source-boundary). Odd-names is committed at db141a57 on the chrome tip. #199 was 7-green on 8850fea9 before the collapse.

New heads are on origin; draft PRs are still missing:
1. cursor/v011-git-revision-source-bd04 @ 69b81956 — base cursor/v011-source-boundary-bd04 (#156); #157–#162
2. cursor/v011-git-revision-content-bd04 @ 0203b174 — base source; #163–#170
3. cursor/v011-git-revision-view-bd04 @ 19ebc64a — base content; #171–#173
4. cursor/v011-git-revision-spa-bd04 @ 039b641b — base view; #174–#178
5. cursor/v011-git-revision-index-bd04 @ c7d5c05b — base spa; #179–#184
6. cursor/v011-git-revision-filters-bd04 @ 317bdd1f — base index; #185–#192
7. cursor/v011-git-revision-chrome-bd04 @ db141a57 — base filters; #193–#199 plus odd-names C0/invalid-UTF-8 display

gh pr create failed: GraphQL/REST "Resource not accessible by integration (createPullRequest)". This VM has GH_TOKEN unset and GITHUB_TOKEN unset (Cloud secrets are not injected into an already-running agent). gh is logged in as cursor[bot] and can read PRs/repo metadata, but repo.permissions are all false and /user is 403. #157–#199 remain open. Do not recreate the seven branches.

Out of scope still: inventory coordinator open, archive containers (mb-380k), serving acquired Git (mb-ew38), CLI --show of a Git pin. Do not close mb-z335. Do not merge. Do not start mb-oueh / mb-ew38 / mb-d658 / mb-380k.
