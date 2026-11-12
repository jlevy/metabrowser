---
type: is
id: is-01m76v9633vk0hrtt21dxxz9bp
title: "PR #362 A3: Reusing the crashed app's PID skips its orphan records"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m76v8wd560c4v4s9c3s6zac4
created_at: 2026-11-12T03:02:07.202Z
updated_at: 2026-11-12T03:31:33.877Z
closed_at: 2026-11-12T03:31:33.871Z
close_reason: "A3 fixed by the stdin lifeline: metab --exit-on-eof (aa48fbe0) and the app passing it with the records and reaper removed (6599e0d9); confirmed by LiveMetabTests.aServerWhoseAppIsGoneStopsByItself and tests/test_stdin_lifeline.py; no per-PID record files exist"
resolution: null
duplicate_of: null
---
Medium finding A3 on PR #362 (apps/macos/ServerRecords.swift:215). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5867906946
