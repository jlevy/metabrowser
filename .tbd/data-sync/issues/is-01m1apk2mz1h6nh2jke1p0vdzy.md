---
type: is
id: is-01m1apk2mz1h6nh2jke1p0vdzy
title: "PR #90 P90-06: --api and --show discard the index result"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:55.262Z
updated_at: 2026-08-31T01:40:12.931Z
closed_at: 2026-08-31T01:40:12.931Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
wait_for_index returns an IndexResult that both modes ignore, so an envelope produced from a failed or timed-out index is printed as if complete.
