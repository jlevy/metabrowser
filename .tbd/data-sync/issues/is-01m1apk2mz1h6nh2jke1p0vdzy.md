---
type: is
id: is-01m1apk2mz1h6nh2jke1p0vdzy
title: "PR #90 P90-06: --api and --show discard the index result"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:55.262Z
updated_at: 2026-08-31T01:22:55.262Z
---
wait_for_index returns an IndexResult that both modes ignore, so an envelope produced from a failed or timed-out index is printed as if complete.
