---
type: is
id: is-01m76bez71jy84fz0j2s9bvzw6
title: "PR #341 A7: the live-server test leaks its child when a request throws"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:39.553Z
updated_at: 2026-11-12T00:03:10.678Z
started_at: 2026-11-12T00:03:10.662Z
---
Medium. apps/macos/Tests/ShellCoreTests/LiveMetabTests.swift:42-55: a throw after start skips subject.stop(). Review A7 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012.
