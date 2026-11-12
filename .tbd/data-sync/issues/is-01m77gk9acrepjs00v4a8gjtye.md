---
type: is
id: is-01m77gk9acrepjs00v4a8gjtye
title: A server launches only from a runtime that passes ExecutableTrust at the moment it spawns
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
created_at: 2026-11-12T09:14:38.282Z
updated_at: 2026-11-12T09:20:51.667Z
started_at: 2026-11-12T09:14:44.488Z
closed_at: 2026-11-12T09:20:51.665Z
close_reason: Fixed in 7979d3e9
resolution: null
duplicate_of: null
---
Review A1 on #377. Trust was checked at discovery, saved-setup admission, and recheck, but FolderServer.mayLaunchNow compared only the cached launchable setup; an ancestor made group-writable, or a link retargeted, while a start waited at the launch gate, launched anyway, since permission and ACL changes do not change the fingerprint. Fix: fresh ExecutableTrust admission for automatically selected runtimes at the moment of spawning, after the gate and termination waits; refusal invalidates the runtime and starts a search; .chosen stays exempt. Tests for a restore and a restart held at the gate.
