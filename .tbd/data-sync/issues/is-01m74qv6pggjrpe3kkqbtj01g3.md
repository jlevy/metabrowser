---
type: is
id: is-01m74qv6pggjrpe3kkqbtj01g3
title: "Stack #350 (merge mode): review, fix, and merge #346, #347, #348, #349, #351"
kind: epic
status: in_progress
priority: 1
version: 8
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
updated_at: 2026-11-11T07:27:41.743Z
started_at: 2026-11-11T07:23:58.705Z
---
User request 2026-11-10: "can you take over this PR stack. Make sure everything is reviewed, fix all issues, and merge everything when done." Native stack #350 on main. Coordinator runs tbd shortcut review-and-merge-prs in merge mode.

## Notes

2026-11-10 round 1 pinned heads: #346 63d5d7fa (base main 87b8ec81), #347 8dd80d0c, #348 e147395f, #349 705d85a1, #351 1db567f7. Worktrees /Users/levy/wrk/github/metabrowser-s350-<N>. Reviews (all strong tier, requested claude-opus-5-5 at xhigh, formal GitHub reviews): 346 A senior; 347 A senior, B security; 348 A senior, B correctness, C security; 349 A senior, B security; 351 A senior + whole-stack assessment. Run in parallel with pre-assigned letters (reviewers read-only in shared trees). Addressing goes bottom-up, merging each fixed layer forward. Merge method: merge commit (repo history), via gh stack merge after the gate passes for every layer. Disk ~3.5 GB free: focused local tests, CI as the full gate.
