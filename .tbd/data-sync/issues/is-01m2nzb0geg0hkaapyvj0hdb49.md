---
type: is
id: is-01m2nzb0geg0hkaapyvj0hdb49
title: "Immutable Git-tree review: publish revision-source PR"
kind: task
status: closed
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - stack:publication
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m2pn3sm2980e2bjnfd3b4xvp
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2pn3sm2980e2bjnfd3b4xvp
hold: null
hold_until: null
created_at: 2026-09-16T20:43:08.685Z
updated_at: 2026-09-23T06:18:33.231Z
started_at: 2026-09-16T21:12:28.728Z
closed_at: 2026-09-23T06:18:33.230Z
close_reason: "Immutable Git-tree review and publication are complete (both spec boxes ticked). #216 was reviewed in the stabilization pass; mb-sumg and the remaining acceptance landed in PR #226 (codex/v012-foundation-stabilization, head f68c3045f40ee28aa3eb37b010511cf8923ccc0d, all nine checks green: https://github.com/jlevy/metabrowser/actions/runs/35825617023), which had two independent reviews with every finding fixed or filed. Published in stack 218; not merged. No URL route claims to serve a repository until Phase 2A."
resolution: null
duplicate_of: null
---
Independently review GitRevisionSubject, GitTreeSource, GitPath, RepositoryStoreTarget migration across every Git consumer and content route, batch framing/cancellation/large-blob behavior, process-safe maintenance locks and durable reachability refs, plugin capability behavior, and two-process concurrent subjects. Resolve findings, run make verify, and publish one formal GitHub PR with gh stacked on exact green mb-tsdc content-source head. Record exact stack/review/CI evidence. Do not merge.

## Notes

2026-09-22 follow-up: no work is held on tbd. All eight current stack PRs are ready for review; #217/#216 draft flags were removed at the user’s request after live ancestry, mergeability and green-CI checks. This changes mechanical mergeability, not feature completion or landing authorization. #216 is ready for review at b3c001a9. Pin acceptance remains open, including mb-sumg and nontrivial golden/browser/installed evidence. Existing focused edge tests are implemented, not wholly missing.

Earlier history:
Immutable Git-tree review now targets draft #216 https://github.com/jlevy/metabrowser/pull/216 (folded #211–#215). Formal PR exists.
--show and non-cache --api pin a file:// revision. HTTP serve / --walk / --check-api still refuse Git sources (mb-ew38).
Unpinned edge tests remain: symlink, gitlink, LFS-pointer, oversized-blob, promisor-miss.
Do not merge.
2026-09-20 correction: the "unpinned edge tests" claim above is out of date. A review on
2026-09-20 found focused tests already on the #216 branch (worktree head de0f4f5a):
tests/test_git_revision_content_routes.py — symlinks (:968, :1032), LFS pointer (:1667),
promisor miss (:1707), gitlink (:388-395); tests/test_git_tree_source.py — oversized blob
(:329), LFS pointer (:638), promisor miss (:677), gitlink (:286-297). The remaining work
for PR #216 is tracked under mb-gacf.

2026-09-22 state reconciliation: draft #216 b3c001a96eed64eb77961c2b7165b103af98b77c is the published integration tip, with all seven checks green. Known edge tests already exist; remaining acceptance is not an absent-PR problem. Track mb-3z4d (nontrivial multi-entry golden and browser evidence), mb-677z (blocking locks on async paths), mb-t7qs (large-blob classification and repeated reads), and new mb-sumg (pin CLI acquisition error mapping). Real CLI/Git 2.50.1 cold/warm/origin-absent file:// smoke passed. Acquired HTTP serving and GitHub URLs/PRs remain future implementation.
