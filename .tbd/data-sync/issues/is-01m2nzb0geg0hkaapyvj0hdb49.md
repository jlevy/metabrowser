---
type: is
id: is-01m2nzb0geg0hkaapyvj0hdb49
title: "Immutable Git-tree review: publish revision-source PR"
kind: task
status: in_progress
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
  - stack:publication
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
updated_at: 2026-09-20T15:45:16.072Z
started_at: 2026-09-16T21:12:28.728Z
---
Independently review GitRevisionSubject, GitTreeSource, GitPath, RepositoryStoreTarget migration across every Git consumer and content route, batch framing/cancellation/large-blob behavior, process-safe maintenance locks and durable reachability refs, plugin capability behavior, and two-process concurrent subjects. Resolve findings, run make verify, and publish one formal GitHub PR with gh stacked on exact green mb-tsdc content-source head. Record exact stack/review/CI evidence. Do not merge.

## Notes

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
