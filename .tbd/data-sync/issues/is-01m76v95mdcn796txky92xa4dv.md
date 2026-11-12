---
type: is
id: is-01m76v95mdcn796txky92xa4dv
title: "PR #362 A2: Batched identity checks leave stale authorization to signal a reused group"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:06.732Z
updated_at: 2026-11-12T03:31:29.340Z
closed_at: 2026-11-12T03:31:29.338Z
close_reason: "A2 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py; no lookup-then-kill remains"
resolution: null
duplicate_of: null
---
High finding A2 on PR #362 (apps/macos/ServerRecords.swift:330). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867906946
