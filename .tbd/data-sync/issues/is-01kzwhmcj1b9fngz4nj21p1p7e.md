---
type: is
id: is-01kzwhmcj1b9fngz4nj21p1p7e
title: Contextual keyboard help and tree navigation
kind: epic
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies: []
child_order_hints:
  - is-01kzwhmd0dc6x7zp924mx1jrb6
  - is-01kzwhmdc3jqvad5w25pdww804
  - is-01kzwhmdrhp7q8g25hh0rrz7yh
  - is-01kzwhme4gyzm3akfkd83vh2sw
created_at: 2026-08-13T03:11:11.425Z
updated_at: 2026-08-13T03:20:23.838Z
---
Implement the active plan for one shortcut registry, a ? Help dialog, persistent and contextual nav hints, Quick File consolidation, and complete accessible file-tree keyboard navigation while preserving native main-pane behavior.

## Notes

Specification drafted and reviewed on codex/help-keyboard-shortcuts. The plan defines one scope-aware registry for dispatch and presentation, an accessible ? Help modal with the public GitHub link, persistent clickable Help and Quick File hints above index progress, contextual tree hints, complete ARIA tree navigation, focus repair across every render path, Quick File migration, and preservation of native preview scrolling. It also consolidates the older menu plan onto the same modal, focused-row, and future F2/Delete shortcut contracts. Full make verify passed with 915 pytest cases and 30 golden scenarios.
