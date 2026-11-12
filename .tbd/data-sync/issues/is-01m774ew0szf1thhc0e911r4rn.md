---
type: is
id: is-01m774ew0szf1thhc0e911r4rn
title: "PR #361 D1: runtime admission expires while the supervisor waits"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m774evh697aew0sqbs5pe9sn
hold: null
hold_until: null
created_at: 2026-11-12T05:42:30.680Z
updated_at: 2026-11-12T05:53:46.555Z
started_at: 2026-11-12T05:42:39.845Z
closed_at: 2026-11-12T05:53:46.553Z
close_reason: "Fixed in 8fbe7d20: runtime checked in mayLaunch at spawn, beside the root check; FolderServerTests."
resolution: null
duplicate_of: null
---
High. FolderServer.swift:44,59; ServerSupervisor.swift:138,186,194. Review D: https://github.com/jlevy/metabrowser/pull/361#pullrequestreview-5869088038
