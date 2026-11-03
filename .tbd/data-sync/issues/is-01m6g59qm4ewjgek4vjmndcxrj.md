---
type: is
id: is-01m6g59qm4ewjgek4vjmndcxrj
title: "Stabilize PR review stacks: rendering, checkout workflows, review gaps, performance"
kind: epic
status: in_progress
priority: 1
version: 11
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m6g5eq1rdb9f15dx2kecf1p0
  - is-01m6g5eqdtdmc5pj1eb9ryy6s1
  - is-01m6g5eqspq97btjbwk0nhwcjw
  - is-01m6g5f41jkfzt0ywcsgxms6j4
  - is-01m6g6cagcckfs78k2ddzs1zz9
  - is-01m6ghtfstncw2xgewnwzvjr6y
  - is-01m6gm8jmy63yqmzcqrvhahnra
hold: null
hold_until: null
created_at: 2026-11-03T07:34:38.973Z
updated_at: 2026-11-03T12:04:25.461Z
started_at: 2026-11-03T07:35:09.898Z
---
Audit stacks 278 and 286, preserve completed reviews, review uncovered changes, stabilize PR rendering for existing worktrees and managed repository stores, and validate through the established performance loop. User authorized subagents and implementation in this session.

## Notes

2026-11-03 takeover progress: all uncovered product changes now have independent source review and fixed-finding rechecks through integrated 64afc0d9. Final real-Chrome QA passed managed repo URL, readonly main and linked checkout subdirectories, file navigation/history/current-file, explicit repair pending/completed/failed/recovered, and light/dark wide/narrow rendering; 25 checkout/common-Git fingerprints unchanged. Font layer 280 is pushed and all nine CI jobs green. Full local gate at64 passed lint/types/contracts/parity and 4647 Python tests with9 legitimate skips; two stale Python comparison-route goldens need owning-layer corrections, alongside two registry transcript updates. Four-doc workflow correction b6a0074c independently reviewed clean. Final forward-only propagation, exact-head full gate, normal push hooks, per-layer remote CI, formal review publication/dispositions and final additive harness remain in progress. No PR merged or history rewritten. Source behavior is frozen pending those gates; Low baseline-matched observer diagnostic tracked in mb-czrw.

2026-11-03 12:00 UTC: finalization held for newly reproduced Medium G1, mb-4vsk. The complete local gate at 58270d69 passed (4,649 Python tests, 373 tryscript checks, audits, distribution/installed-wheel smokes); eight live public GitHub tests passed. A separate independent real-route probe then reproduced stale exact counts after corruption-time invalidation fails in a read-only manifest bank, backing objects are repaired, and process state restarts. Owning-head reproduction at #283 3cb49015 confirms this is lower-layer code. The normal atomic push was stopped during its quality hook with exit 130, and all seven source remote heads were verified unchanged. The exact-head acceptance driver was stopped cleanly: all 51 owned processes gone and validation ports free. Its full audit and partial raw data/browser evidence are preserved, not claimed as final acceptance. The earlier complete 64afc0d9 diagnostic has zero unexplained product differences. Writer is implementing a bounded private epoch fallback outside the bank plus nonmutating adoption eligibility checks, including permission restoration and stale in-flight writes. After independent recheck, root will merge forward, repeat exact-head gates and acceptance, then push normally and watch CI. No PR has been merged; port 8863 remains untouched.
