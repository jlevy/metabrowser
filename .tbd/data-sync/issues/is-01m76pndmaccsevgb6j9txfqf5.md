---
type: is
id: is-01m76pndmaccsevgb6j9txfqf5
title: "PR #359 B3: a size-valid session can trigger unbounded native-window creation"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76pmzm35hysy66g7kva9k09
hold: null
hold_until: null
created_at: 2026-11-12T01:41:25.257Z
updated_at: 2026-11-12T01:53:58.893Z
started_at: 2026-11-12T01:41:34.143Z
closed_at: 2026-11-12T01:53:58.892Z
close_reason: "Fixed in f6623bd5: RestoreBudget.standard (20 windows, 50 tabs, measured basis beside the constant) cuts the session before admission and building. SavedSessionTests.aHostileSessionBuildsOnlyTheBudget."
resolution: null
duplicate_of: null
---
Medium. apps/macos/Sources/Metabrowser/FolderWindows.swift:216 and :225. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867702230.
