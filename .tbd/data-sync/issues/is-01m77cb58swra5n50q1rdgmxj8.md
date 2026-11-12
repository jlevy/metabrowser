---
type: is
id: is-01m77cb58swra5n50q1rdgmxj8
title: A selected restored root that now leads to another folder joins that folder's session
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
created_at: 2026-11-12T08:00:17.687Z
updated_at: 2026-11-12T08:21:40.277Z
started_at: 2026-11-12T08:00:26.912Z
closed_at: 2026-11-12T08:21:40.276Z
close_reason: "Fixed in 494f28cf: a selected restored root that now leads to another folder moves its tabs to that folder's session (RestoreRun, RootActivation, RestoreQueue.redirect), with RestoredAliasTests for the review's trace."
resolution: null
duplicate_of: null
---
Review C1 on #363 (mb-niod). Selecting a restored root that waited under its saved spelling only cleared its launch check, so a saved folder A replaced by a link to B started a server for B keyed under A: opening B or a file in it started a second server, and with B restored too, selecting A did. Fix: resolve a selected root before its start; one that now leads to another folder moves its tabs to that folder's session (the open one, else a new one), leaves the restore, and the canonical root starts next as the user's choice unless it is already open. Decision in ShellCore with tests, plus an integrated regression: restore A, relink A to B, select A, open B or a file in it, one server.
