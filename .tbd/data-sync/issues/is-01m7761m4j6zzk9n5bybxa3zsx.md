---
type: is
id: is-01m7761m4j6zzk9n5bybxa3zsx
title: "PR #361 E2: a root-refused upgrade restart shows Starting and selection cannot recover it"
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
created_at: 2026-11-12T06:10:13.778Z
updated_at: 2026-11-12T06:17:12.275Z
started_at: 2026-11-12T06:10:26.833Z
closed_at: 2026-11-12T06:17:12.274Z
close_reason: "Fixed in ed4ce997: refusedByRoot settled to waiting for selection and held in the restore queue; aRootRefusedRestartWaitsForItsTabAndStartsOnceSelected; app glue by inspection."
resolution: null
duplicate_of: null
---
Medium. FolderSession.swift:115,121; FolderWindows.swift:98. Review E: https://github.com/jlevy/metabrowser/pull/361#pullrequestreview-5869885468
