---
type: is
id: is-01kzwhmdc3jqvad5w25pdww804
title: Migrate Quick File commands and hints to the shared registry
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhme4gyzm3akfkd83vh2sw
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:12.258Z
updated_at: 2026-08-13T03:50:35.385Z
---
Remove Quick File’s duplicate global listener and HINT_GROUPS data; register T, slash, result movement, open, and Escape in the correct scopes; port Quick File to the shared dialog and overlay lifecycle; derive all labels, keycaps, separators, spoken names, and valid-or-omitted ARIA values from shared presentation data; and preserve editable-target, composition, search, modal, and focus-restoration behavior.
