---
type: is
id: is-01m6f3aa89emxbf0rwesa8gt7x
title: Tree rendering with the Files tree's contract
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies:
  - type: blocks
    target: is-01m6f3aapq93hetda33rkdc9zv
parent_id: is-01m6f39zpnk9rc3kjy552b88qj
created_at: 2026-11-02T21:40:46.472Z
updated_at: 2026-11-03T02:48:41.818Z
---
Row markup, chevrons, child groups, change badges, and inline stats, with the gesture and keyboard split through tree-keyboard-navigation.js handed by the host, the current row auto-expanded, and paths painted as text through the display rule.

## Notes

2026-11-02, coordinator decision from #285 review A5: step 3's addressing makes the Pulls list role=tree with treeitem rows (aria-level) and scopes the Files tree's keyboard handler to the Files panel, so step 4 only adds children: a .tree-children[role=group] per row and aria-expanded on a row that has them. Key moves replace the history entry and a click or Enter pushes (A1), for file rows too.
