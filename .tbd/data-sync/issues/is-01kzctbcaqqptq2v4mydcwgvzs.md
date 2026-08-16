---
type: is
id: is-01kzctbcaqqptq2v4mydcwgvzs
title: "Menu and overlay primitives: anchored placement, action menu, action registry, inline edit"
kind: feature
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctbjy7z530930gzmvakxws
created_at: 2026-08-07T00:35:42.550Z
updated_at: 2026-08-16T08:05:43.325Z
extensions:
  linear:
    id: 01ac05ee-899f-410e-9948-efa3e2753f08
    linked_at: 2026-08-16T08:05:43.325Z
---
Phase 1 of the menu-primitives plan. Implement the shared anchored/modal overlay layer, action menu, contextual action registry, and inline editor; port Quick File, tooltip placement, and settings onto the shared overlay; register disabled rename/trash actions as the first context-menu consumers; and add strict DOM tests and design-system documentation. Coordinate the modal foundation with keyboard-help bead mb-zxi0. Reuse the complete tree focus/navigation contract from mb-67ru and do not add a competing minimal roving-tabindex handler.
