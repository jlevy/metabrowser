---
type: is
id: is-01m76v9e4ardhd3rdarnah2qcs
title: "PR #362 C6: Recovery input lacks the ownership and bounded-read checks needed before signalling"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:15.433Z
updated_at: 2026-11-12T03:32:38.408Z
closed_at: 2026-11-12T03:32:38.365Z
close_reason: "C6 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py; no recovery input is read"
resolution: null
duplicate_of: null
---
High finding C6 on PR #362 (apps/macos/ServerRecords.swift:223). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867907659
