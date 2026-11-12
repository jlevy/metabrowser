---
type: is
id: is-01m76zwx021154vnkbmsb80kq5
title: Test fake servers exit on stdin EOF so a crashed test run leaks nothing
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T04:22:47.553Z
updated_at: 2026-11-12T04:22:47.553Z
---
From the #341 CI investigation: when the test process crashed (a SIGPIPE, since fixed), childIgnoringTermIsKilledAfterTheGrace left its shell orphaned, because it traps TERM and ignores its stdin lifeline; 13 orphans had to be killed by hand. Make the fake and fixture servers exit when their stdin reaches EOF.
