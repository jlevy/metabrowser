---
type: is
id: is-01m76v99sc379wf7ga6qpdswp2
title: "PR #362 B2: A matching process need not be a safe group leader"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:10.987Z
updated_at: 2026-11-12T03:32:04.025Z
closed_at: 2026-11-12T03:32:03.962Z
close_reason: "B2 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py; no record names a group to signal"
resolution: null
duplicate_of: null
---
High finding B2 on PR #362 (apps/macos/ServerRecords.swift:329). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867907207
