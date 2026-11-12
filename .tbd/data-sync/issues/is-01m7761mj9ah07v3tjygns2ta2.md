---
type: is
id: is-01m7761mj9ah07v3tjygns2ta2
title: "PR #361 E3: startedRuntime is recorded before the child is created"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7761k9b4gdeynpg22ag21zt
hold: null
hold_until: null
created_at: 2026-11-12T06:10:14.216Z
updated_at: 2026-11-12T06:17:12.653Z
started_at: 2026-11-12T06:10:27.260Z
closed_at: 2026-11-12T06:17:12.651Z
close_reason: "Fixed in ed4ce997: ServerSupervisor.onSpawn records startedRuntime; SpawnBookkeepingTests (red at d3f7cc6f)."
resolution: null
duplicate_of: null
---
Medium. FolderServer.swift:126; ServerSupervisor.swift:208. Review E: https://github.com/jlevy/metabrowser/pull/361#pullrequestreview-5869885468
