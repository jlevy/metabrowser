---
type: is
id: is-01m77gk9sdnbcmwq1jmcs83adw
title: Selecting a restored root whose start waits at the launch gate reconciles its identity first
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T09:14:38.764Z
updated_at: 2026-11-12T09:24:55.542Z
started_at: 2026-11-12T09:14:44.863Z
closed_at: 2026-11-12T09:24:55.540Z
close_reason: Fixed in 6340e6f7
resolution: null
duplicate_of: null
---
Review A2 on #377. A tab selected while its root's start waited at the launch gate cleared the root check, but queue.select returned false for the outstanding root, so canonical reconciliation never ran and the saved spelling launched, serving the folder it now leads to under the saved key. Fix: such a selection makes the outstanding attempt resolve its path at the moment of spawning; a path that now leads to another folder refuses the spawn and the run moves its tabs before any child spawns. RestoreRunTests with a held launch gate; README limitation removed.
