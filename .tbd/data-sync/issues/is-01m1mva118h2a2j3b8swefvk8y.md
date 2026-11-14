---
type: is
id: is-01m1mva118h2a2j3b8swefvk8y
title: "PR #101 R4: host-side debts behind the inventory boundary"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md
labels: []
dependencies: []
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
created_at: 2026-09-03T23:57:45.894Z
updated_at: 2026-11-14T18:47:10.342Z
---
DEFER (post-merge). Host-side debts behind the inventory boundary, from the PR #101 review (docs/project/reviews/review-2026-09-07-inventory-stack-merge-readiness.md). That review fixed read_session holding the coordinator lock across provider awaits. Remaining: (b) SSE reconnects start from a fresh snapshot rather than resuming deltas (src/metabrowser/events_route.py:714-716), so reset, disconnect, and reconnect storms re-run full snapshots; (c) /api/tree's UNKNOWN-path loop retries full assemblies every 5 ms (src/metabrowser/server.py:2384-2396), and the rollup route's ETag keys on the global engine sequence; (d) per-connection scope filtering happens after events enter the bounded queue; (e) coordinator._history's worst case retains about 4.2M strings.

## Notes

Fixed read_session serialization in the PR101 final review: a root operation lease and immutable sparse overlay snapshot let overlay publication and unrelated reads continue during provider I/O. Regression pauses a page read, applies an overlay change, then proves the session retains its original overlay/cursor. Remaining work: SSE bus snapshot lock/resume, scope filtering before per-client queues, history memory, UNKNOWN retries, and global validators. See docs/project/reviews/review-2026-09-07-inventory-stack-merge-readiness.md.

2026-09-20: status returned to open (was in_progress). PR #101 is MERGED, mergedAt
2026-09-09T00:14:52Z (verified with gh pr view 101), so the review round itself is over,
but the residuals listed above (SSE bus snapshot lock/resume, scope filtering before
per-client queues, history memory, UNKNOWN retries, global validators) remain real,
unclaimed work. Nothing is in flight, so in_progress overstated it.
