---
type: is
id: is-01kzwmp9d6mgn76qgtpxvb70qz
title: Build Help and contextual navigation hints
kind: feature
status: closed
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhmdc3jqvad5w25pdww804
  - type: blocks
    target: is-01kzwhmdrhp7q8g25hh0rrz7yh
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T04:04:39.461Z
updated_at: 2026-08-13T05:45:05.687Z
closed_at: 2026-08-13T05:45:05.685Z
close_reason: Implemented and verified the registry-driven Help dialog, approved project copy/link, stable actionable and contextual nav hints, shell asset order, application composition, styling, and disposal.
---
TDD src/metabrowser/static/keyboard_help.js and tests/dom/keyboard_help_behavior.js. Implement renderHelpGroups(), reconcileHintStrip(), and create() through the registry and shared modal. Register help.close, construct the modal against that command, then register help.open with its control binding; render the approved description, safe public GitHub link, exact ordered groups, shared binding DOM, keyed persistent actionable Help and Quick File buttons, action-only accessible button names, and active non-live contextual hints. Preserve persistent trigger nodes across scope updates; connect surface-owned control bindings; carry pointer triggers through invoke() for focus restoration; forward resolveFocusFallback; rebuild full Help only on registration changes. In app.js add application-lifetime shortcutRegistry/keyboardHelp handles, initKeyboardInfrastructure(), and resolveApplicationFocusFallback(); initialize Help before Quick File, with the later tree bead extending the same composition function. In server.py:index(), add #nav-shortcut-hints immediately above unchanged #index-progress and load/cache-bust keyboard_shortcuts.js, overlay_layer.js, and keyboard_help.js before consumers; the later tree-integration bead extends that order with tree_keyboard_navigation.js. Add token-only Help and wrapping nav-chrome styles plus internal types. Dispose control bindings, modal, registrations, subscription, and DOM.
