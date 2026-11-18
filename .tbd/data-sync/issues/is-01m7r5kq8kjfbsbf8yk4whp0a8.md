---
type: is
id: is-01m7r5kq8kjfbsbf8yk4whp0a8
title: "Flake: test_recent_targets concurrent writers hit the 2 s lock wait on loaded CI"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T20:29:43.551Z
updated_at: 2026-11-18T21:02:22.945Z
started_at: 2026-11-18T21:02:22.944Z
---
Main CI run 44386715486 at a1100bca6: unit (3.14t, 2/2) failed tests/test_recent_targets.py:803 (writers * each <= MAX_RECENT_TARGETS case) with RecentTargetsError 'another Metabrowser process has held the recent targets list for 2 seconds' (BlockingIOError EAGAIN). The test's concurrent writers can exceed the lock wait on a loaded free-threaded runner.
