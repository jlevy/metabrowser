---
type: is
id: is-01m76v9556pvcyvh336x5wtk0k
title: "PR #362 A1: Recovery files are trusted without validating ownership and permissions"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:06.245Z
updated_at: 2026-11-12T03:31:25.372Z
closed_at: 2026-11-12T03:31:25.371Z
close_reason: "A1 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py; no recovery file is read"
resolution: null
duplicate_of: null
---
High finding A1 on PR #362 (apps/macos/ServerRecords.swift:226). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867906946
