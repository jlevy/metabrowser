---
type: is
id: is-01kzwhmdc3jqvad5w25pdww804
title: Migrate Quick File commands and hints to the shared registry
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhme4gyzm3akfkd83vh2sw
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:12.258Z
updated_at: 2026-08-13T03:11:13.039Z
---
Remove Quick File's duplicate global open listener and HINT_GROUPS data; register slash/T, result movement, open, and Escape in the correct scopes; derive its inline hints from shared presentation data while preserving editable-target, composition, search, modal, and focus-restoration behavior.
