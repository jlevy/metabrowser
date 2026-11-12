---
type: is
id: is-01m76bey17ghd77vj1zyy3jt86
title: "PR #341 A4/C3: an older discovery overwrites a newer explicit runtime choice"
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
created_at: 2026-11-11T22:25:38.342Z
updated_at: 2026-11-12T00:14:50.050Z
started_at: 2026-11-12T00:03:11.440Z
closed_at: 2026-11-12T00:14:50.049Z
close_reason: "fixed in ffb196b1 (A4/C3): RuntimeSelection tickets, newest operation wins; RuntimeSelectionTests"
resolution: null
duplicate_of: null
---
Medium. apps/macos/Sources/Metabrowser/AppDelegate.swift:245-258, RuntimeWindow.swift:45: a Find Again finishing after Choose metab saves its own result over the choice, or clears it on failure. Reviews: A4 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012, C3 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036572.
