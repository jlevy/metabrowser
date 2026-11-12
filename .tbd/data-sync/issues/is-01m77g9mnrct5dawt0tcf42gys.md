---
type: is
id: is-01m77g9mnrct5dawt0tcf42gys
title: "Review H1 on #363: a lifeline test can miss the harness's \"cleaning\" line"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T09:09:22.231Z
updated_at: 2026-11-12T09:09:50.405Z
started_at: 2026-11-12T09:09:30.657Z
closed_at: 2026-11-12T09:09:50.403Z
close_reason: 'Fixed in b3d59ede (#363): the signal-during-cleanup test listens for "cleaning" from the moment the harness is spawned.'
resolution: null
duplicate_of: null
---
processes.test.mjs's signal-during-cleanup test subscribed to "cleaning" only after ownedChild() returned, so a stdout chunk carrying both "ready" and "cleaning" was consumed first and the wait timed out. Listen from the start.
