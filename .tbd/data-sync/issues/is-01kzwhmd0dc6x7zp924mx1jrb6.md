---
type: is
id: is-01kzwhmd0dc6x7zp924mx1jrb6
title: Build the shortcut registry, shared Help dialog, and persistent nav hints
kind: feature
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhmdc3jqvad5w25pdww804
  - type: blocks
    target: is-01kzwhmdrhp7q8g25hh0rrz7yh
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:11.884Z
updated_at: 2026-08-13T03:50:35.145Z
---
TDD the strict keyboard_shortcuts and keyboard_help modules under the durable design-system contract: validate centralized group and copy descriptors; generate canonical visible and spoken binding forms plus only accurate physical-key ARIA values; keep one document dispatcher; reuse the shared dialog anatomy with inert background, scoped Escape, focus restoration, and disposal; implement the approved Help content and persistent ? plus T-or-slash hints; and add cross-surface, script-order, and package-asset coverage.
