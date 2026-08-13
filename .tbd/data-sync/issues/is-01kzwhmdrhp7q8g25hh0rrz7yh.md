---
type: is
id: is-01kzwhmdrhp7q8g25hh0rrz7yh
title: Add ARIA file-tree keyboard navigation and contextual hints
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhme4gyzm3akfkd83vh2sw
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:12.656Z
updated_at: 2026-08-13T03:11:13.039Z
---
TDD the strict tree navigator; add tree/treeitem/group roles, roving tabindex, expanded/selected/level state, visible-row traversal, arrow/Home/End/Enter/Space behavior, paginated and lazy activation, and focus repair across filters, source repaints, and live mutations. Show tree hints only while tree focus makes them available.
