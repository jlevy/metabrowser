---
type: is
id: is-01m856rcj9syg0ndntv31degzt
title: Diff | Current moves to the diff's toolbar beside Split | Unified; Changes opens on Diff, Docs on Current
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m84zd2x1v206rxsr1fspew62
hold: null
hold_until: null
created_at: 2026-11-23T21:59:52.647Z
updated_at: 2026-11-23T22:00:32.994Z
started_at: 2026-11-23T22:00:32.992Z
---
User decision 2026-11-23: the chooser belongs to the diff as a whole, not each file bar. On Changes it sits next to Split | Unified in the toolbar; on Docs in the same place (Docs has no layout control, so the toolbar holds Diff | Current). Changes (and a commit page, a patch) default to Diff; Docs defaults to Current. Each surface remembers its own choice, so a choice on one does not change the other's default.
