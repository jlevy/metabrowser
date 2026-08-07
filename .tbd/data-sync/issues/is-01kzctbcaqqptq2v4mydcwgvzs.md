---
type: is
id: is-01kzctbcaqqptq2v4mydcwgvzs
title: "Menu and overlay primitives: anchored placement, action menu, action registry, inline edit"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctbjy7z530930gzmvakxws
created_at: 2026-08-07T00:35:42.550Z
updated_at: 2026-08-07T00:36:02.580Z
---
Phase 1 of the menu-primitives plan. Extract one anchored-overlay primitive (point and element anchors, flip-and-clamp, dismissal, focus save/restore, single-open arbitration, disposal) plus a modal variant; port search_palette.js and the tooltip's clamping onto it; add action_menu.js (roving focus, ARIA roles, text-node labels), action_registry.js (context resolution, capability-aware enablement), and inline_edit.js; wire the nav-tree contextmenu and keyboard openers with a placeholder action set; port the settings gear onto the shared overlay; add .menu-item.destructive and .menu-item-hint; Node DOM tests for each module; document the placement/content/command layers in docs/design-system.md. No user-visible mutation lands in this phase.
