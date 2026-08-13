---
type: is
id: is-01kzwhmd0dc6x7zp924mx1jrb6
title: Build the shortcut registry and binding presentation system
kind: feature
status: open
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhmdc3jqvad5w25pdww804
  - type: blocks
    target: is-01kzwhmdrhp7q8g25hh0rrz7yh
  - type: blocks
    target: is-01kzwmp3cfc54f78nzrzdnbn5v
  - type: blocks
    target: is-01kzwmp9d6mgn76qgtpxvb70qz
  - type: blocks
    target: is-01kzwmpf6yhydjd4btqdz0gpd4
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:11.884Z
updated_at: 2026-08-13T04:11:51.639Z
---
TDD src/metabrowser/static/keyboard_shortcuts.js and tests/dom/keyboard_shortcuts_behavior.js. Implement KEY_DEFINITIONS and GROUP_DEFINITIONS; normalizeBinding(), bindingSignature(), eventMatchesBinding(), isEditableTarget(), validateCommand(), describeBindings(), appendBinding(), and create({document}). The factory must provide register, activateScope, invoke(commandId, context), snapshot, structured subscription events, presentation helpers, and disposal around exactly one capture-phase document dispatcher. Validate descriptor copy, control bindings, and duplicate bindings; preserve stable group/command order; carry frozen surface-owned control bindings; derive canonical visible, spoken, and valid-or-omitted physical-key ARIA representations; preserve native behavior for unhandled, editable, composing, modified, and disallowed repeat events. Add strict global declarations to static/types.d.ts.
