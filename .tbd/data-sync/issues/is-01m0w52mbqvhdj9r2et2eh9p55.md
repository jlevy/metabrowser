---
type: is
id: is-01m0w52mbqvhdj9r2et2eh9p55
title: "Spec: Git revision navigation performance"
kind: epic
status: open
priority: 1
version: 54
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
  - is-01m0ycrwkzbfjdbf19t8tpevjp
  - is-01m0yec42r62gm91em9p25vne3
  - is-01m0yh4s21r569a73k1kaz8p35
  - is-01m0yjwamztrrcqs6e5gf1x9wn
  - is-01m0yjwbybpt8r9bf1pjehswr0
created_at: 2026-08-25T09:47:28.502Z
updated_at: 2026-08-26T08:27:12.201Z
---
Deliver the complete phased plan in docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md: reviewed Git revision navigation, file/Git readiness parity, request deduplication, stable hover, O(1) selection feedback, standard interaction attribution, corrected input-relative driver timing, performance instrumentation, live-folder panel-state repair, and the final no-fade foreground-arrival contract. Keep useful retained content and the light/dark pane canvas visually unchanged while loading; preserve one claim-owned nonvisual busy lifecycle; animate only incoming foreground content from 0.98 to 1 over 50 ms; keep row work proportional to changed rows; distinguish selection feedback from painted readiness and Event Timing; exclude driver preparation from application timing; retain at most one speculative comparison; cancel obsolete work; and fail standard scenarios on fanout, duplicate selected work, blank frames, stuck busy state, missing attribution, route/render divergence, folder-state freezing, exceptions, or forced layout. Add no unmeasured cache, dependency, or speculative compatibility. Close only after PR #82 is retargeted from its stack and the final exact-head CI is green.

## Notes

All implementation phases are complete through exact pushed PR #82 head 301b450. This includes retained file/Git navigation, connected inert async file staging with atomic handoff and claim-owned stale cleanup, pointer-only navigation tooltips, corrected strong-pure/pale-paired/strong-intraline diff hierarchy, semantic gutter bars, Split-first layout order and default, shared design-system contracts, and standard browser performance gates. make verify passes 1,562 tests plus 48 golden scenarios; exact-headed file and Git scenarios have zero blank frames or state divergence; all current GitHub checks are green. The final globally installed build is metabrowser 0.7.2.dev48+301b450 and serves the large representative repository at http://127.0.0.1:8770/view/. Epic remains open only for the explicit stacked delivery gate: land PR #81, retarget PR #82 to main without losing commits, repeat exact-head validation and final CI, then close.
