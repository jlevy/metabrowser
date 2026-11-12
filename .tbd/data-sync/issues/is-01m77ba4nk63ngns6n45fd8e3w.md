---
type: is
id: is-01m77ba4nk63ngns6n45fd8e3w
title: "Review B3 on #363: the SIGKILL test races the fixture's trap"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T07:42:15.730Z
updated_at: 2026-11-12T08:02:42.728Z
started_at: 2026-11-12T07:42:21.747Z
closed_at: 2026-11-12T08:02:42.727Z
close_reason: "Fixed in 4244b34f (#363): the SIGKILL fixture prints ready after its trap and the test waits for it, bounded at 10 s, stopping the fixture on failure."
resolution: null
duplicate_of: null
---
processes.test.mjs could send SIGTERM before the shell fixture installed trap '' TERM. Wait for a readiness line printed after the trap, with a bounded timeout, and stop the fixture on failure.
