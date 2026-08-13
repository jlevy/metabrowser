---
type: is
id: is-01kzwhmd0dc6x7zp924mx1jrb6
title: Build the shortcut registry, shared Help dialog, and persistent nav hints
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhmdc3jqvad5w25pdww804
  - type: blocks
    target: is-01kzwhmdrhp7q8g25hh0rrz7yh
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:11.884Z
updated_at: 2026-08-13T03:11:12.656Z
---
TDD the strict keyboard_shortcuts and keyboard_help modules; reuse or extract the shared overlay modal contract; implement scope arbitration, guards, presentation snapshots, disposal, the approved Help copy and GitHub link, and the always-visible ? plus T/slash hint strip above index progress. Add script-order and package-asset coverage.
