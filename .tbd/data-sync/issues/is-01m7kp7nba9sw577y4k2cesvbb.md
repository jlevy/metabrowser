---
type: is
id: is-01m7kp7nba9sw577y4k2cesvbb
title: Python provider reports unreadable directories as complete and empty (R6, D1)
kind: bug
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kp7r5gs472n9g927516cpk
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:02.026Z
updated_at: 2026-11-17T02:44:04.912Z
---
walker.py treats PermissionError and vanished directories as empty with coverage complete, never emitting inaccessible coverage or a permission issue. Report honestly and merge the three disagreeing host status helpers into one that distinguishes complete-with-issues from discovering. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, D1.
