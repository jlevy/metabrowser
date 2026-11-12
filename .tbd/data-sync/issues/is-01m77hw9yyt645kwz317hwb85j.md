---
type: is
id: is-01m77hw9yyt645kwz317hwb85j
title: A selected restored root's later restart after a relink ends at the folder it leads to
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
created_at: 2026-11-12T09:37:02.429Z
updated_at: 2026-11-12T09:41:48.106Z
started_at: 2026-11-12T09:37:08.329Z
closed_at: 2026-11-12T09:41:48.105Z
close_reason: Fixed in 8b832c64
resolution: null
duplicate_of: null
---
Review B1 on #377. A2's spawn-time identity check stayed on a root after its selected start succeeded; a later relink and Restart Server was refused by it, and rootRefused's hold returned early for a selected root, so the root was in neither pending nor deferred and reselecting it started nothing. Fix: a selected restored root keeps the identity check for its later starts, a refusal requeues it as the user's choice and runs the restore, which moves its tabs to the canonical folder's session; a background root started earlier and selected later gets the same. Tests through relink, restart refusal, and recovery to one canonical server.
