---
type: is
id: is-01m76xfs2fn2tebk6d1ezv0kdv
title: Set MetabRequirement.isReleased when metab 0.12.1 is published
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T03:40:40.395Z
updated_at: 2026-11-20T17:15:05.551Z
closed_at: 2026-11-20T17:15:05.547Z
close_reason: Superseded by mb-1d8p, whose PR B sets MetabRequirement.isReleased with the 0.13.0 floor; detail merged into mb-1d8p's notes
resolution: duplicate
duplicate_of: is-01m7hhr43k5rc7ytbxg1vx031s
---
From #361: until 0.12.1 is on PyPI, the app's first-run steps end in make install in a source checkout plus Choose metab, because the upgrade command cannot succeed. The release that publishes 0.12.1 must set MetabRequirement.isReleased = true (apps/macos/Sources/ShellCore/Setup/MetabVersion.swift) and its docs.
