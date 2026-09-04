---
type: is
id: is-01m1mva118h2a2j3b8swefvk8y
title: "PR #101 R4: host-side debts behind the inventory boundary"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:45.894Z
updated_at: 2026-09-03T23:57:45.894Z
---
DEFER (post-merge). (a) read_session holds the coordinator lock across every provider await of a multi-page assembly while change publication needs the same lock; reset -> SSE disconnect -> reconnect storms re-run full snapshots under it. (b) SSE reconnects never resume deltas though a 4,096-deep history exists. (c) /api/tree's UNKNOWN-path loop re-runs full assemblies every 5ms; the rollup route's ETag keys on the global engine sequence. (d) Per-connection scope filtering happens after events enter the bounded queue. (e) coordinator._history worst case is ~4.2M retained strings.
