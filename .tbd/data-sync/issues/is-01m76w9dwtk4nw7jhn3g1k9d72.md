---
type: is
id: is-01m76w9dwtk4nw7jhn3g1k9d72
title: "PR #359 E1: admission can become stale while waiting for the launch gate"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76w98xw4agt7w0m6csrsacn
hold: null
hold_until: null
created_at: 2026-11-12T03:19:43.725Z
updated_at: 2026-11-12T03:42:35.440Z
started_at: 2026-11-12T03:19:49.074Z
closed_at: 2026-11-12T03:42:35.438Z
close_reason: "Fixed in 0a6c0108: ServerSupervisor.mayLaunch checked after the gate and termination waits, just before spawn; refused roots wait (RestoreQueue.hold); selection clears the check. RestoreLaunchTests. Reply issuecomment-6813723631."
resolution: null
duplicate_of: null
---
High. FolderWindows.swift:281, ServerSupervisor.swift:181. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5868421803.
