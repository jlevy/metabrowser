---
type: is
id: is-01m76bez71jy84fz0j2s9bvzw6
title: "PR #341 A7: the live-server test leaks its child when a request throws"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:39.553Z
updated_at: 2026-11-12T00:14:51.133Z
started_at: 2026-11-12T00:03:10.662Z
closed_at: 2026-11-12T00:14:51.132Z
close_reason: "fixed in 28c90f7d (A7): stoppingAfterward helper; SupervisedProcessTests throw and cancel cases; live tests pass"
resolution: null
duplicate_of: null
---
Medium. apps/macos/Tests/ShellCoreTests/LiveMetabTests.swift:42-55: a throw after start skips subject.stop(). Review A7 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012.
