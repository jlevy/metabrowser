---
type: is
id: is-01m77cvd155rssacrafna2gz5e
title: "Docs: a closed stdin may stop the server before its banner (#366 review B4)"
kind: task
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
created_at: 2026-11-12T08:09:09.924Z
updated_at: 2026-11-12T08:36:41.724Z
started_at: 2026-11-12T08:09:18.242Z
closed_at: 2026-11-12T08:36:41.723Z
close_reason: Fixed in b7edb5d3 on claude/cli-exit-on-eof (#366 review B4).
resolution: null
duplicate_of: null
---
Review B on #366, B4: docs/command-line.md guaranteed a banner ordering the watch does not enforce.
