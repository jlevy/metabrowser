---
type: is
id: is-01m76bexmw16j8tg4w8d0n9ybc
title: "PR #341 A3/C4: Restart keeps the runtime chosen before Settings changed it"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:37.947Z
updated_at: 2026-11-12T00:14:49.688Z
started_at: 2026-11-12T00:03:11.073Z
closed_at: 2026-11-12T00:14:49.687Z
close_reason: "fixed in ffb196b1 (A3/C4): Retry/Restart Server rebuild the command from the current runtime; RuntimeSwitchTests"
resolution: null
duplicate_of: null
---
Medium. apps/macos/Sources/Metabrowser/FolderSession.swift:63 and AppDelegate.swift:310: each session's LaunchSpec is fixed at creation, so Retry and Restart ignore a newly chosen metab despite the notice. Reviews: A3 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012, C4 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036572.
