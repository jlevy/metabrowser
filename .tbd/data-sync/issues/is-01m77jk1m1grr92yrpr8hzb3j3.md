---
type: is
id: is-01m77jk1m1grr92yrpr8hzb3j3
title: A restored start that completes after its last tab closed is not recorded as started
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
created_at: 2026-11-12T09:49:27.552Z
updated_at: 2026-11-12T09:51:45.553Z
started_at: 2026-11-12T09:49:33.315Z
closed_at: 2026-11-12T09:51:45.552Z
close_reason: Fixed in 128d2169
resolution: null
duplicate_of: null
---
Review C1 on #377. RestoreQueue.finish inserted into started even after remove had invalidated the outstanding attempt, so a root whose last tab closed while its start waited at the gate was re-added when the cancelled attempt returned .launched, and a later reopened session of that path was treated as restored. Fix: finish records started only for the outstanding attempt. Regression with a held gate, a close, and a reopen.
