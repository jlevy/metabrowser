---
type: is
id: is-01m77ba4nk63ngns6n45fd8e3w
title: "Review B3 on #363: the SIGKILL test races the fixture's trap"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T07:42:15.730Z
updated_at: 2026-11-12T07:42:21.748Z
started_at: 2026-11-12T07:42:21.747Z
---
processes.test.mjs could send SIGTERM before the shell fixture installed trap '' TERM. Wait for a readiness line printed after the trap, with a bounded timeout, and stop the fixture on failure.
