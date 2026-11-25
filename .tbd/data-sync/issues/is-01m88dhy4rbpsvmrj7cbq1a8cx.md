---
type: is
id: is-01m88dhy4rbpsvmrj7cbq1a8cx
title: "PR #811 A3: a withheld fold's fetch shows no progress and fails silently"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:56:24.599Z
updated_at: 2026-11-25T03:59:32.346Z
started_at: 2026-11-25T03:59:32.343Z
---
Medium. diff-markdown.js toggleFold (1476-1511), askFold (1535-1553). Only aria-busy marks the request; on failure the bar closes with a console.warn. Show the file progress mark while fetching and leave a quiet mark on failure (design-system-messages.md, Degrade Gracefully). Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
