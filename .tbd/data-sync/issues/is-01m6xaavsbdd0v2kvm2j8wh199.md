---
type: is
id: is-01m6xaavsbdd0v2kvm2j8wh199
title: Prevent late prefetch receipts from advancing a restarted pass
kind: bug
status: in_progress
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6wdjwshpc22fta0bf5mwwbs
hold: null
hold_until: null
created_at: 2026-11-08T10:12:46.506Z
updated_at: 2026-11-08T10:24:12.134Z
started_at: 2026-11-08T10:13:09.850Z
---
Independent correctness review B1 reproduced on ea1c5ace26195bcf7205275c40f3c516dea9c4ce. With600 catalog rows, hold a ready All receipt for rows440..433, revise already-covered row460 beyond the held500-row prefix, accept revision, then deliver the old receipt. Base revisits460 and completes600/600; new head completes599/600 with zero timers and never requests460 in the new generation. holdEnvelope restarts traversal while retaining the old producer, then sendCoreWindow advances warmAfter from that old demand. Preserve valid admitted producer ownership, but allow traversal cursor/visible-cohort advancement only for the pass/revision that created the demand. Add the concise production-session regression before full gate. Evidence late-receipt-probe.cjs/log in private b0aq-independent-review-20261108; no latency claim. Root reserves commits/PR/merge; do not alter backend attempt leases.

## Notes

B1 corrected in forward commit 1ede1e22044fa662ef48f261e7d830ca9f0b897f atop ea1c5ace. A CoreDemand records a traversal pass independently of owner epoch. Obsolete terminal replies settle their actual owner, then queue the current pass without applying cursor, viewport coverage, deferred deadline, retry reset or pause effects. Started/joined retained work still polls until settlement. Six600-row cases are red-to-green (ready, partial, failed, busy, not_owner, invalid coverage); changed460 is requested under newgeneration, all600 finish, no timers. Focused checks and normal commit hooks pass. Independent follow-up D is in progress; full gate, PR/CI/merge/install remain pending. Evidence B1-handoff.json; no timing claim.
