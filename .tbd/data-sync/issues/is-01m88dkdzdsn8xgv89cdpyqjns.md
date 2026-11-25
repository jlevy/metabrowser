---
type: is
id: is-01m88dkdzdsn8xgv89cdpyqjns
title: "PR #811 A7: a failed Full upgrade overrides a choice made while it was in flight"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:57:13.573Z
updated_at: 2026-11-25T03:59:37.794Z
started_at: 2026-11-25T03:59:37.792Z
---
Low. diff-markdown.js askFull catch 1270-1276 sets file.mode back even when the reader chose another view meanwhile; fall back only while file.mode is full. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
