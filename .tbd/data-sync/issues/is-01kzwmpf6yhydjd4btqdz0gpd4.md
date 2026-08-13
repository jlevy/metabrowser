---
type: is
id: is-01kzwmpf6yhydjd4btqdz0gpd4
title: Build the strict tree keyboard navigator
kind: feature
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhmdrhp7q8g25hh0rrz7yh
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T04:04:45.405Z
updated_at: 2026-08-13T06:09:37.574Z
closed_at: 2026-08-13T06:09:37.569Z
close_reason: Added the strict tree navigator with semantic synchronization, roving focus, durable repair, scope-aware commands, pointer continuity, and exhaustive DOM behavior tests; make verify passes with 922 tests.
---
TDD src/metabrowser/static/tree_keyboard_navigation.js and tests/dom/tree_keyboard_navigation_behavior.js. Implement rowIdentity(), readVisibleRows(), parentRow(), firstChildRow(), setAnchor(), repairAnchor(), prepareForMutation(), synchronize(), registerCommands(), and create(). Own flattened visible-row traversal, durable identity, roving tabindex, focus repair, tree-scope activation, contextual command registration, pointer/focus synchronization, and disposal. synchronize() repairs owned-group relationships, level/position/set metadata, selected/expanded state, and the visible snapshot after every mutation. Movement allows repeat; activation does not. Delegate folder, leaf, symlink, lazy, and pagination actions through callbacks; arrow-only movement never opens a preview and known-empty folders remain end nodes. Add internal types to static/types.d.ts.
