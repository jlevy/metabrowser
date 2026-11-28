---
type: is
id: is-01m8hq84zmhe33jz9a5cshevys
title: Explain incomplete SoftSchema indexes with a spaced, actionable notice
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/932
    at: 2026-11-28T19:00:34.910Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cnf3htjx8gp16bqgxjxjdw
hold: null
hold_until: null
created_at: 2026-11-28T18:38:59.570Z
updated_at: 2026-11-28T19:00:34.911Z
started_at: 2026-11-28T18:41:48.574Z
---
Use existing bounded collection problem codes to explain skipped, unreadable, or out-of-budget coverage. Avoid treating record validation findings as missed index coverage. Give the shared warning notice space below it and test both partial and complete states.

## Notes

The collection Table view now reads coverage codes from summary.problems and distinguishes scan limits, oversized files, unreadable paths and unreadable names; record validation errors alone do not trigger a warning. Incomplete snapshots of unknown coverage have a plain fallback. Scoped table stylesheet applies the shared block spacing token after a notice. The browserless table-view transcript passed all five checks; 43 reader-message and collection-route tests passed; three browser type-check projects passed. Both observed live scopes were complete; the user's earlier transient cannot be attributed to a specific cause.
