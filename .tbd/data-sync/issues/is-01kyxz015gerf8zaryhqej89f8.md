---
type: is
id: is-01kyxz015gerf8zaryhqej89f8
title: "Spike 5: build the accessible slash-key finder palette"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxz08ne4mbst6q9t742f808
parent_id: is-01kyxyb67v18br7jm7w8mrwss5
created_at: 2026-08-01T06:08:17.070Z
updated_at: 2026-08-01T06:08:24.749Z
---
Use TDD to add search_palette as a thin controller consumer and wire the slash shortcut outside editable, composing, modified, already-prevented, and palette-input events. Implement bounded result DOM, basename and parent-path labels, highlighted match ranges, empty and incomplete states, Arrow Up and Down, Home, End, Enter, Escape, pointer selection, outside-click dismissal, focus restoration, and labelled dialog plus combobox and listbox semantics. Reuse design tokens and inject actions rather than reading private app globals.
