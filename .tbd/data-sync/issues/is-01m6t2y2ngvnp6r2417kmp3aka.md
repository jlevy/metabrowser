---
type: is
id: is-01m6t2y2ngvnp6r2417kmp3aka
title: Use provider-time provenance for PR arrival tint under clock skew
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T04:05:44.238Z
updated_at: 2026-11-07T04:05:44.238Z
---
The conservative PR arrival baseline compares GitHub created_at with this machine and browser timestamps. A fast clock can suppress the arrival tint while the catalog row and its normal selection/status still render. Reuse GitHub response Date from existing conditional provider reads and monotonic elapsed time, with persisted provenance and warm/cache-only/backfill/reconnect tests. Do not add provider requests or infer unsafe offsets. The existing fetched_at field is also local time, so replacing Math.max with fetched_at alone cannot correct this local-server case.
