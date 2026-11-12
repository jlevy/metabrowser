---
type: is
id: is-01m76xfs2fn2tebk6d1ezv0kdv
title: Set MetabRequirement.isReleased when metab 0.12.1 is published
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T03:40:40.395Z
updated_at: 2026-11-12T03:40:40.395Z
---
From #361: until 0.12.1 is on PyPI, the app's first-run steps end in make install in a source checkout plus Choose metab, because the upgrade command cannot succeed. The release that publishes 0.12.1 must set MetabRequirement.isReleased = true (apps/macos/Sources/ShellCore/Setup/MetabVersion.swift) and its docs.
