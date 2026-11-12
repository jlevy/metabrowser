---
type: is
id: is-01m77cc9z9k9nvtpfxc6qy4w4m
title: A stop kills owned groups from the kernel's child list, bounded, without the event loop (#366 review B1)
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T08:00:55.270Z
updated_at: 2026-11-12T08:00:55.270Z
---
Review B on #366, B1: shutdown still depended on an in-flight spawn returning; the signal path had no bounded completion; a failed set-up balanced the counter without owning what was forked.
