---
type: is
id: is-01m0w52mbqvhdj9r2et2eh9p55
title: "Spec: Git revision navigation performance"
kind: epic
status: open
priority: 1
version: 36
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
child_order_hints:
  - is-01m0w52zzfx6qf6qf8536jxcxh
  - is-01m0w539fx31x7vj0rv24twqmm
  - is-01m0w53j45t8y2p1w9kka5b9t7
  - is-01m0w53vkse6krjp4g03k5x7q6
  - is-01m0wq55zyfz7g5r55k9h6ntyv
  - is-01m0wrpxfbmxdjaew4e3v6w19s
  - is-01m0wrpxv4phv1x1q6a7h9cnns
  - is-01m0wtb8g8gjxbm6d5m9zqv5bh
  - is-01m0ww2gzdqqmkx8gjfjd5gct0
  - is-01m0wycyj5gpp5gh1eyczfcrcp
  - is-01m0x2ayvesqex8163ch5n72s5
  - is-01m0x3rc6p6dnwj5qhnjhavqtz
  - is-01m0x3rwk2zj4vweea5c0a2sq1
  - is-01m0x3rx12rgkb5pgdasd1zwn4
  - is-01m0x3sawfqnqshvkb4rqz54yq
  - is-01m0x52zqfhdqp9jdg82p4299j
  - is-01m0x3skec67w78kafbez3xj2d
  - is-01m0w542g2gzak7th85hx2bdz8
  - is-01m0xp9057jb8f0pcjhch592qd
  - is-01m0xp910y4k86s1emzcn93rz0
  - is-01m0xtc5n71qyfhgd9p1nzxcws
created_at: 2026-08-25T09:47:28.502Z
updated_at: 2026-08-26T01:18:55.654Z
---
Deliver the twenty-phase plan in docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md: the reviewed Git revision navigation implementation and its later file/Git parity, request-deduplication, visible pending-sheet, stable-hover, O(1) selection-feedback, standard performance-instrumentation, and final PR/CI phases. Keep useful content visible; use one compositor-friendly pointer-transparent pending sheet over the preview only; keep row interaction work proportional to the changed rows; distinguish immediate selection feedback from selection-to-painted-ready and Event Timing; retain at most one speculative comparison; cancel obsolete work; fail standard scenarios on fanout, duplicate selected work, blank frames, stuck pending state, missing phase attribution, or route/render divergence; do not add unmeasured caching, dependencies, or speculative compatibility; close only after PR #82 has exact-head green CI.

## Notes

Twenty-phase implementation now includes the user-acceptance refinements: a single 60 ms compositor-friendly pending sheet, stable-hover network intent, instant row backgrounds, old/new-only selected-row mutation, post-readiness roving Tab finalization, gitRevision:selectionFeedback and gitRevision:rowAnchor attribution, and stricter headed Git health validation. Final fixed-corpus capture shows immediate feedback at 4.5 ms or less with pending onset in 11.4–16.1 ms, zero blank frames, exact selected/route/rendered convergence, one mount, bounded deferred hydration, and zero obsolete successes. Await final full verification, commit/push, PR review/CI, and exact-build handoff before closing.
