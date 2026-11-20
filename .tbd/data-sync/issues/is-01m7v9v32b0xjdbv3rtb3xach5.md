---
type: is
id: is-01m7v9v32b0xjdbv3rtb3xach5
title: "PR #617 B15: extensionless SQLite files (Chrome History, Cookies) never reach the magic rule"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v9tw8y6ssgdghdyks2p5ty
hold: null
hold_until: null
created_at: 2026-11-20T01:41:22.635Z
updated_at: 2026-11-20T01:57:23.630Z
started_at: 2026-11-20T01:50:18.958Z
closed_at: 2026-11-20T01:57:23.630Z
close_reason: "fixed in 74df98ad5: magic checked for extensionless files; extensionless databases open, no chevron, reached by opening"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:379-390. Suggestion: say how such a file opens. Severity: Suggestion. PR #617. Review: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5986230518
