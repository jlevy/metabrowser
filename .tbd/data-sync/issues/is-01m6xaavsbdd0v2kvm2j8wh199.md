---
type: is
id: is-01m6xaavsbdd0v2kvm2j8wh199
title: Prevent late prefetch receipts from advancing a restarted pass
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6wdjwshpc22fta0bf5mwwbs
created_at: 2026-11-08T10:12:46.506Z
updated_at: 2026-11-08T10:12:46.506Z
---
Independent correctness review B1 reproduced on ea1c5ace26195bcf7205275c40f3c516dea9c4ce. With600 catalog rows, hold a ready All receipt for rows440..433, revise already-covered row460 beyond the held500-row prefix, accept revision, then deliver the old receipt. Base revisits460 and completes600/600; new head completes599/600 with zero timers and never requests460 in the new generation. holdEnvelope restarts traversal while retaining the old producer, then sendCoreWindow advances warmAfter from that old demand. Preserve valid admitted producer ownership, but allow traversal cursor/visible-cohort advancement only for the pass/revision that created the demand. Add the concise production-session regression before full gate. Evidence late-receipt-probe.cjs/log in private b0aq-independent-review-20261108; no latency claim. Root reserves commits/PR/merge; do not alter backend attempt leases.
