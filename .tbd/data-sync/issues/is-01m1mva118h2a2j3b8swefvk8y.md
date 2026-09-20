---
type: is
id: is-01m1mva118h2a2j3b8swefvk8y
title: "PR #101 R4: host-side debts behind the inventory boundary"
kind: task
status: open
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:45.894Z
updated_at: 2026-09-20T15:42:22.008Z
---
DEFER (post-merge). (a) read_session holds the coordinator lock across every provider await of a multi-page assembly while change publication needs the same lock; reset -> SSE disconnect -> reconnect storms re-run full snapshots under it. (b) SSE reconnects never resume deltas though a 4,096-deep history exists. (c) /api/tree's UNKNOWN-path loop re-runs full assemblies every 5ms; the rollup route's ETag keys on the global engine sequence. (d) Per-connection scope filtering happens after events enter the bounded queue. (e) coordinator._history worst case is ~4.2M retained strings.

## Notes

Fixed read_session serialization in the PR101 final review: a root operation lease and immutable sparse overlay snapshot let overlay publication and unrelated reads continue during provider I/O. Regression pauses a page read, applies an overlay change, then proves the session retains its original overlay/cursor. Remaining work: SSE bus snapshot lock/resume, scope filtering before per-client queues, history memory, UNKNOWN retries, and global validators. See docs/project/reviews/review-2026-09-07-inventory-stack-merge-readiness.md.

2026-09-20: status returned to open (was in_progress). PR #101 is MERGED, mergedAt
2026-09-09T00:14:52Z (verified with gh pr view 101), so the review round itself is over,
but the residuals listed above (SSE bus snapshot lock/resume, scope filtering before
per-client queues, history memory, UNKNOWN retries, global validators) remain real,
unclaimed work. Nothing is in flight, so in_progress overstated it.
