---
type: is
id: is-01m76v97dygz4k2y2e2xdjddar
title: "PR #362 A6: A log offset does not isolate output from concurrent app copies"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:08.573Z
updated_at: 2026-11-12T03:31:49.330Z
closed_at: 2026-11-12T03:31:49.325Z
close_reason: "A6 fixed in cbcb3c11: ServerLogLease gives a second running copy its own log; LogLeaseTests"
resolution: null
duplicate_of: null
---
Medium finding A6 on PR #362 (apps/macos/ChildLog.swift:63). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867906946
