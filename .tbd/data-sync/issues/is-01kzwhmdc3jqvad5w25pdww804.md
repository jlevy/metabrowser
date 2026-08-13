---
type: is
id: is-01kzwhmdc3jqvad5w25pdww804
title: Migrate Quick File commands and hints to the shared registry
kind: task
status: closed
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhme4gyzm3akfkd83vh2sw
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:12.258Z
updated_at: 2026-08-13T05:58:13.795Z
closed_at: 2026-08-13T05:58:13.794Z
close_reason: Quick File now registers every command and hint with the shared registry, uses the shared modal lifecycle and control binding, and retains search, focus, and catalog behavior; make verify passes with 921 tests.
---
Refactor src/metabrowser/static/search_palette.js under TDD in tests/dom/search_palette_behavior.js. Remove OPEN_KEYS, HINT_GROUPS, hintGroup(), isEditableTarget(), handleGlobalKeydown(), and the palette document listener. Require shared shortcuts and overlay inputs; register quick-file.close, construct the modal against that command, then add registerCommands() and renderShortcutHints() for quick-file.open, previous, next, first, last, and activate in global or modal scope with correct editable/composition/repeat policy. Attach the modal control binding to the open descriptor, pass a pointer trigger through invoke/open, forward resolveFocusFallback for replaced tree or preview nodes, and route Close/scrim/Escape through the same registered handler. Route all keycaps, separators, spoken names, copy, and valid-or-omitted ARIA through registry presentation and appendBinding(). Retain palette open/close API, pinned-Tab behavior, search, stale-result, catalog-growth, cancellation, pointer, and focus-destination behavior. Update app.js:initQuickFileFinder() to inject application-lifetime infrastructure and add structural integration assertions.
