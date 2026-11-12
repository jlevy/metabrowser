---
type: is
id: is-01m76v96h43bqx2r7rpc15qwhm
title: "PR #362 A4: Failed survivor persistence still deletes the last recovery evidence"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:07.652Z
updated_at: 2026-11-12T03:31:38.910Z
closed_at: 2026-11-12T03:31:38.888Z
close_reason: "A4 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py; no survivor transfer exists"
resolution: null
duplicate_of: null
---
Medium finding A4 on PR #362 (apps/macos/ServerRecords.swift:155). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867906946
