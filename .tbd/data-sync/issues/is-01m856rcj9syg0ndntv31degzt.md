---
type: is
id: is-01m856rcj9syg0ndntv31degzt
title: Diff | Current moves to the diff's toolbar beside Split | Unified; Changes opens on Diff, Docs on Current
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m84zd2x1v206rxsr1fspew62
hold: null
hold_until: null
created_at: 2026-11-23T21:59:52.647Z
updated_at: 2026-11-23T22:46:14.450Z
started_at: 2026-11-23T22:00:32.992Z
closed_at: 2026-11-23T22:46:14.445Z
close_reason: "Diff | Current moved to the diff's toolbar beside Split | Unified, Docs' toolbar back; Changes/commit/patch open on Diff (diff.show), Docs on Current (github.docs.show); N on the toolbar chooser. Commit ea47ce06a, merged #766's branch at 07d37cf0c, PR #765 rebased onto claude/rendered-diff-no-content-refusals."
resolution: null
duplicate_of: null
---
User decision 2026-11-23: the chooser belongs to the diff as a whole, not each file bar. On Changes it sits next to Split | Unified in the toolbar; on Docs in the same place (Docs has no layout control, so the toolbar holds Diff | Current). Changes (and a commit page, a patch) default to Diff; Docs defaults to Current. Each surface remembers its own choice, so a choice on one does not change the other's default.
