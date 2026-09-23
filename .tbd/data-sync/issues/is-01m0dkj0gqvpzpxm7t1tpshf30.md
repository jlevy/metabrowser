---
type: is
id: is-01m0dkj0gqvpzpxm7t1tpshf30
title: "Repository projection: immutable Git-tree source over a shared object store"
kind: feature
status: closed
priority: 1
version: 86
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2kw2bht6rte4gtjdq39n1yt
  - type: blocks
    target: is-01m2nzb0geg0hkaapyvj0hdb49
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2zvd48wxye9c7f3py7s14nq
hold: null
hold_until: null
created_at: 2026-08-19T18:11:56.054Z
updated_at: 2026-09-23T06:18:32.931Z
started_at: 2026-09-16T21:10:44.836Z
closed_at: 2026-09-23T06:18:32.930Z
close_reason: "The immutable Git-tree source is implemented in #216. Its remaining acceptance is in PR #226 (codex/v012-foundation-stabilization, head f68c3045f40ee28aa3eb37b010511cf8923ccc0d, all nine checks green: https://github.com/jlevy/metabrowser/actions/runs/35825617023): installed-CLI T0 walkthrough, multi-entry golden, R5 and memo regressions, windowed large-blob reads (mb-t7qs), async-lock fixes (mb-677z), lazy-fetch acceptance on real admitted Git, the Git 2.43 refused-fetch handling, symlink bounds, and stale ref-lock recovery (mb-2k9c). HTTP serving is Phase 2A (mb-ew38)."
resolution: null
duplicate_of: null
---
Implement GitRevisionSubject and GitTreeSource over a shared RepositoryStoreTarget and an opaque SourceSession. Define byte-segment GitPath identity and URL/display serialization; enumerate NUL-framed trees with stable byte ordering; read blobs through exclusive actor-style cat-file batch readers that issue info before contents, enforce size gates, drain frames, and poison/restart on cancellation or framing failure. Migrate history, repo discovery, commit detail, refs, diffs, file/raw/container/classification/KPress routes, and built-in sidekicks to exact target plus subject OID semantics. Protect live OIDs with cross-process shared maintenance locks and durable private refs; GC/repack takes the exclusive lock. Add crash/stale-lock recovery, promisor-miss, oversized-blob, invalid-UTF8/newline-name, and two-process/two-OID tests. Never create a checkout, index, branch, worktree, or fake filesystem fact.

## Notes

2026-09-22 follow-up: no work is held on tbd. All eight current stack PRs are ready for review; #217/#216 draft flags were removed at the user’s request after live ancestry, mergeability and green-CI checks. This changes mechanical mergeability, not feature completion or landing authorization. Focused symlink, gitlink, LFS-pointer, oversized-blob, promisor-miss and odd-name tests exist. Remaining work is the tracked CLI/installed/golden and performance/error-boundary acceptance. HTTP serving remains Phase2A/mb-ew38, not a prerequisite for completing this source implementation.

Earlier history:
Implementation is on draft #216 https://github.com/jlevy/metabrowser/pull/216. Formal PR exists. --show / non-cache --api lease a file:// pin. HTTP serving is mb-ew38, not this bead.

Remaining on this bead: focused tests for symlink, gitlink, LFS-pointer, oversized-blob, and promisor-miss (newline and invalid-UTF-8 GitPaths are already on the branch). Review is mb-hoae.
2026-09-20 correction: the "unpinned edge tests" claim above is out of date. A review on
2026-09-20 found focused tests already on the #216 branch (worktree head de0f4f5a):
tests/test_git_revision_content_routes.py — symlinks (:968, :1032), LFS pointer (:1667),
promisor miss (:1707), gitlink (:388-395); tests/test_git_tree_source.py — oversized blob
(:329), LFS pointer (:638), promisor miss (:677), gitlink (:286-297). The remaining work
for PR #216 is tracked under mb-gacf.
