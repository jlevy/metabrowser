---
type: is
id: is-01m7761kpm70fbmf2betjhbgfc
title: "PR #361 E1: putBack loses a selection made while the restore was starting"
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
created_at: 2026-11-12T06:10:13.332Z
updated_at: 2026-11-12T06:17:11.794Z
started_at: 2026-11-12T06:10:26.435Z
closed_at: 2026-11-12T06:17:11.793Z
close_reason: "Fixed in ed4ce997: RestoreQueue tracks the outstanding root and its selections; RestorePauseTests (red at d3f7cc6f)."
resolution: null
duplicate_of: null
---
Medium. SavedSession.swift:180,198; FolderWindows.swift:287. Review E: https://github.com/jlevy/metabrowser/pull/361#pullrequestreview-5869885468
