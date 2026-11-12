---
type: is
id: is-01m76v9a9xmrgkqdvnjkfkyxev
title: "PR #362 B3: Identity checks do not protect the subsequent signal from PID/group reuse"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:11.516Z
updated_at: 2026-11-12T03:32:09.806Z
closed_at: 2026-11-12T03:32:09.771Z
close_reason: "B3 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py (the lifeline option of the finding)"
resolution: null
duplicate_of: null
---
High finding B3 on PR #362 (apps/macos/ServerRecords.swift:330). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867907207
