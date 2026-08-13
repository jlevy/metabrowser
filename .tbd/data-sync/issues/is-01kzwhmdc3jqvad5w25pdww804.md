---
type: is
id: is-01kzwhmdc3jqvad5w25pdww804
title: Migrate Quick File commands and hints to the shared registry
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhme4gyzm3akfkd83vh2sw
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:12.258Z
updated_at: 2026-08-13T04:11:58.829Z
---
Refactor src/metabrowser/static/search_palette.js under TDD in tests/dom/search_palette_behavior.js. Remove OPEN_KEYS, HINT_GROUPS, hintGroup(), isEditableTarget(), handleGlobalKeydown(), and the palette document listener. Require shared shortcuts and overlay inputs; add registerCommands() and renderShortcutHints(); register quick-file.open, previous, next, first, last, activate, and close in global or modal scope with correct editable/composition/repeat policy; attach the modal control binding to the open descriptor and pass a pointer trigger through invoke/open; route all keycaps, separators, spoken names, copy, and valid-or-omitted ARIA through registry snapshots and appendBinding(). Port direct overlay DOM and local focus/Escape lifecycle to MetabrowserOverlay.createModal() while retaining palette open/close API, pinned-Tab behavior, search, stale-result, catalog-growth, cancellation, pointer, and focus-destination behavior. Update app.js:initQuickFileFinder() to inject application-lifetime infrastructure and add structural integration assertions.
