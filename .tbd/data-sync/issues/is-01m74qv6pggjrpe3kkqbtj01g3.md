---
type: is
id: is-01m74qv6pggjrpe3kkqbtj01g3
title: "Stack #350 (merge mode): review, fix, and merge #346, #347, #348, #349, #351"
kind: epic
status: closed
priority: 1
version: 11
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m74qv74fxdqpx51jpxnsmeh9
  - is-01m74qv7hbqxtkan4pevshgfq8
  - is-01m74qv7yahzvdr77eq6wp2rev
  - is-01m74qv8b02t85rv9cam272wqj
  - is-01m74qv8qsq8mywe4cdxzfmc5z
hold: null
hold_until: null
created_at: 2026-11-11T07:23:34.467Z
updated_at: 2026-11-11T16:56:20.110Z
started_at: 2026-11-11T07:23:58.705Z
closed_at: 2026-11-11T16:56:20.109Z
close_reason: "Stack #350 (#346, #347, #348, #349, #351) reviewed (23 published reviews, every finding dispositioned), merged to main as ab346bf8 on 2026-11-11 via gh stack merge with merge commits; post-merge CI run 43060650224 on main green. Follow-ups: mb-273l (stoppable document renderer), mb-x0sv (public KPress per-block API), mb-5rth (paired startup timing), epic mb-c93s (spinner-free refresh and prefetch)."
resolution: null
duplicate_of: null
---
User request 2026-11-10: "can you take over this PR stack. Make sure everything is reviewed, fix all issues, and merge everything when done." Native stack #350 on main. Coordinator runs tbd shortcut review-and-merge-prs in merge mode.

## Notes

2026-11-10 round 1 pinned heads: #346 63d5d7fa (base main 87b8ec81), #347 8dd80d0c, #348 e147395f, #349 705d85a1, #351 1db567f7. Worktrees /Users/levy/wrk/github/metabrowser-s350-<N>. All reviews strong tier, requested claude-opus-5-5 at xhigh, formal GitHub reviews by jlevy, verified at the pinned heads.
Round 1 reviews: #346 A senior (1M 6L 3S) review-5855482052. #347 A senior (1H 10M 6L 2S) review-5855504972; B security (1M 1L 1S) review-5855525387; C correctness (3M 5L) review-5855769655. #348 A senior (9M 5L 1S) review-5855514600; B correctness (2M 3L) review-5855560340; C security (1M 1L) review-5855484116; D performance (1H 1M 2L) review-5855776380. #349 A senior (1H 6M 7L 2S) review-5855490584; B security (1H 2L) review-5855503638; C performance (1H 3M 1L 1S) review-5855871513. #351 A senior + whole stack (1H 7M 8L) review-5855489961; whole-stack items name owning layers.
Addressing: one opus-xhigh agent per layer, merge-forward (no rebase/force-push), push --no-verify after focused tests + lint-check, CI is the full gate (disk ~3.5 GB). #346 addressing pushed 9c625f4e, 6c1bc550.

2026-11-11 progress: #346 done after 3 rounds (A, B, C), final 6d924fd3, CI 43004721258 green. #347 rounds 1-2 addressed (A, B, C, D), head 86261188 CI 43011593273 green; round-3 follow-up E running (security of hashed page scripts). #348 round 1 addressed (A-D, 26 findings), head 4640580e CI 43012470833 green; layer grew to +4,257 lines, so round-2 follow-ups E (correctness) and F (security+performance) running. #349 phase 1 pushed 6167e89f (projection worker process, hidden-change signatures); phase 2 started on 4640580e. #351 not yet addressed. Incident: a plain make lint-check (install prerequisite, npm ci) through a symlinked node_modules emptied the primary checkout's node_modules; restored with npm ci; every worktree now has its own copy. Two stray headless Chrome processes (19919, 27828) reported to the user.
