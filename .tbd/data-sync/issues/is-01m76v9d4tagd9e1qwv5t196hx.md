---
type: is
id: is-01m76v9d4tagd9e1qwv5t196hx
title: "PR #362 C5: Failed survivor adoption still deletes the original recovery records"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:14.425Z
updated_at: 2026-11-12T03:32:33.699Z
closed_at: 2026-11-12T03:32:33.689Z
close_reason: "C5 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py; no survivor adoption exists"
resolution: null
duplicate_of: null
---
Medium finding C5 on PR #362 (apps/macos/ServerRecords.swift:155). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867907659
