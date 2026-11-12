---
type: is
id: is-01m76qyyf19mj2ya9fsydmj4mv
title: "PR #361 A2/C1: the upgrade offer restarts folders whose servers never started"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76qyxmt9sy6zr9ffwqe0eqs
hold: null
hold_until: null
created_at: 2026-11-12T02:04:05.984Z
updated_at: 2026-11-12T03:38:08.522Z
started_at: 2026-11-12T02:04:20.197Z
closed_at: 2026-11-12T03:38:08.508Z
close_reason: "Fixed in f58eb702: startedRuntime only from an actual launch (A2, C1); FolderServerTests.anUpgradeOffersToRestartOnlyServersThatStarted."
resolution: null
duplicate_of: null
---
High. AppDelegate.swift:525, FolderSession.swift:35 (runtime set at construction). Reviews A2, C1: https://github.com/jlevy/metabrowser/pull/361
