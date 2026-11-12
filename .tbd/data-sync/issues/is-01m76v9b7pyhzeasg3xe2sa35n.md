---
type: is
id: is-01m76v9b7pyhzeasg3xe2sa35n
title: "PR #362 C1: Orphan signals are not bound to the checked process incarnation"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:12.469Z
updated_at: 2026-11-12T03:32:14.866Z
closed_at: 2026-11-12T03:32:14.841Z
close_reason: "C1 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py"
resolution: null
duplicate_of: null
---
Blocker finding C1 on PR #362 (apps/macos/ServerRecords.swift:329). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867907659
