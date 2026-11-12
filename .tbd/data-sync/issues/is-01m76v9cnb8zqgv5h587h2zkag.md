---
type: is
id: is-01m76v9cnb8zqgv5h587h2zkag
title: "PR #362 C4: Reuse of the app's own PID bypasses orphan discovery"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:13.930Z
updated_at: 2026-11-12T03:32:28.809Z
closed_at: 2026-11-12T03:32:28.751Z
close_reason: "C4 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py; no per-PID record files exist"
resolution: null
duplicate_of: null
---
Medium finding C4 on PR #362 (apps/macos/ServerRecords.swift:215). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867907659
