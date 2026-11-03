---
type: is
id: is-01m6ge33szvtwd0mrs6mwa5aq5
title: "PR #283 F2: recycle stale pooled readers after successful object recovery"
kind: bug
status: in_progress
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6g5f41jkfzt0ywcsgxms6j4
created_at: 2026-11-03T10:08:19.262Z
updated_at: 2026-11-03T11:44:11.322Z
---
Independent Review F at4dcbc0dd primes two real pack readers, detects corruption in one, repairs/replaces the backing pack, then authenticates recovery with fresh actors. Another pooled actor retains the unlinked old corrupt pack: later reads alternate genuine/object_corrupt after success. Checkout writer owns safe generation-based retirement including checked-out leases, with negative-control regression; no lender writes or abrupt cancellation of active readers.

## Notes

Implemented in 48036bf7ee9d159b7b185adfee993c84d3728ea4 on codex/overlay-healing-01a1a051; clean isolated worktree. Independent F2 probe reproduced by two real packed-object regressions (idle and checked-out retained readers), both failed before fix. Explicit recovery advances reader-pool generation after fresh object verification and before clearing failures. Idle actors are reaped immediately; active exclusive leases finish untouched then recycle on release; waiters never acquire an obsolete generation. Cancellation returns all drained slots as stale for later recycling. Five focused F2 regressions pass, including saturated waiter and one/two-slot cancellation. Affected window/tree/overlay suite:189 passed; final changed-source BasedPyright:0 errors; normal commit hooks passed. Author self-review is not independent; awaiting root final review/integration. Root owns sync, pushes and closure.

2026-11-03 independent-review integration at final tip 58270d69. Review F2 is independently verified fixed at ce634f90, retained at owning #283 3cb49015. Real repaired-pack probes return genuine bytes from both slots; idle, active-lease, waiter, and cancellation cases pass without interrupting active transactions. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
