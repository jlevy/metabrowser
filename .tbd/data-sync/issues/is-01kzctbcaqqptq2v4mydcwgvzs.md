---
type: is
id: is-01kzctbcaqqptq2v4mydcwgvzs
title: "Menu and overlay primitives: anchored placement, action menu, action registry, inline edit"
kind: feature
status: open
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctbjy7z530930gzmvakxws
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-08-07T00:35:42.550Z
updated_at: 2026-11-20T19:15:58.097Z
extensions: {}
---
Phase 1 of the menu-primitives plan (docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md). Already on main: the modal half of static/overlay-layer.js (createModal) with Quick File and keyboard help on it (#35), the shortcut registry (mb-zxi0), and the tree focus contract (mb-67ru). Remaining: point and element anchoring with flip-and-clamp and the anchored dismissal contract in overlay-layer.js; positionTooltip's clamping on the shared placement helper; action-menu.js, action-registry.js, and inline-edit.js; the nav-tree context menu with rename and trash descriptors rendered disabled; porting the settings gear onto the overlay; Node DOM tests; and the design-system review. Reuse the tree focus contract; add no second tree-navigation handler.
