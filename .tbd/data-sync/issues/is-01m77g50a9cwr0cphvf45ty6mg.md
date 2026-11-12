---
type: is
id: is-01m77g50a9cwr0cphvf45ty6mg
title: A stop signals only a child confirmed unreaped (#366 review C1)
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T09:06:50.312Z
updated_at: 2026-11-12T09:08:35.617Z
started_at: 2026-11-12T09:08:35.616Z
---
Review C on #366, C1: registered entries skipped the returncode guard, and a listed child reaped before the signal could leave its ID to a new group.
