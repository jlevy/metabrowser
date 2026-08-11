---
type: is
id: is-01kzsbqnwk75ebmrgrvw8nph3j
title: "PR #24 review R16: HEAD ring shows a sidebar-coloured disc when selected"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-11T21:30:24.530Z
updated_at: 2026-08-11T21:30:47.967Z
closed_at: 2026-08-11T21:30:47.966Z
close_reason: Fixed on feat/git-graph-view; covered by tests that fail without the fix.
---
The hollow HEAD and merge markers follow the row background so they read as a ring rather than a filled dot, but only the default and hover backgrounds had rules. A selected row showed a sidebar-coloured disc inside the ring. Fixed with a .git-graph-row.selected rule ordered after the hover rule, matching how the equal-specificity row background itself resolves; a structural test pins the ordering.
