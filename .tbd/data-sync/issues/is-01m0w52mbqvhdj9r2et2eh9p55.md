---
type: is
id: is-01m0w52mbqvhdj9r2et2eh9p55
title: "Spec: Git revision navigation performance"
kind: epic
status: open
priority: 1
version: 48
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
  - is-01m0xvd71f9wvm3127ewrytsjd
  - is-01m0xwh9tfjnqf5rfb3dpap7cb
  - is-01m0xyc7gj5qhj6w8sz58qdf4m
  - is-01m0y2pmcc6nvcze73d3s39jm3
created_at: 2026-08-25T09:47:28.502Z
updated_at: 2026-08-26T06:26:37.067Z
---
Deliver the complete phased plan in docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md: reviewed Git revision navigation, file/Git readiness parity, request deduplication, stable hover, O(1) selection feedback, standard interaction attribution, corrected input-relative driver timing, performance instrumentation, live-folder panel-state repair, and the final no-fade foreground-arrival contract. Keep useful retained content and the light/dark pane canvas visually unchanged while loading; preserve one claim-owned nonvisual busy lifecycle; animate only incoming foreground content from 0.98 to 1 over 50 ms; keep row work proportional to changed rows; distinguish selection feedback from painted readiness and Event Timing; exclude driver preparation from application timing; retain at most one speculative comparison; cancel obsolete work; and fail standard scenarios on fanout, duplicate selected work, blank frames, stuck busy state, missing attribution, route/render divergence, folder-state freezing, exceptions, or forced layout. Add no unmeasured cache, dependency, or speculative compatibility. Close only after PR #82 is retargeted from its stack and the final exact-head CI is green.

## Notes

All implementation phases are complete through current PR #82 head 5caa1e0, with exact-head CI green and final stack-tip browser validation passing. The severe large-folded-diff regression discovered during handoff is fixed under mb-t44x on the base branch and merged into this head; it reduces the exact 19,654-line comparison from 182,686 to 6,476-6,679 DOM nodes and from a 552 ms to 127 ms longest task, with zero collapsed hidden rows. The final globally installed stack tip is metab 0.7.2.dev44+0bd3d5b and all plugins pass doctor. The epic remains open only because its explicit acceptance requires #81 to land, #82 to be retargeted to main, and final post-stack CI to pass.
