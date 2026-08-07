---
type: is
id: is-01kzctbcaqqptq2v4mydcwgvzs
title: "Menu and overlay primitives: anchored placement, action menu, action registry, inline edit"
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-06-menu-primitives-and-file-actions.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzctbjy7z530930gzmvakxws
created_at: 2026-08-07T00:35:42.550Z
updated_at: 2026-08-07T00:52:49.754Z
---
Phase 1 of the menu-primitives plan (see spec). Extract one anchored-overlay primitive: point and element anchors, flip-and-clamp with max-height internal scroll, anchored dismissal contract (opening event immune; internal scroll never dismisses), focus save/restore with detached-element fallback, one shared document Escape router, single-open arbitration (one anchored + one modal, no stack), disposal; body-portal is required correctness (preview-pane transform creates a fixed-position containing block). Modal variant with minimal Tab wrap; port search_palette.js onto it AFTER the quick-file branch lands; move positionTooltip clamping onto the shared helper. action_menu.js: roving focus, focusable disabled rows with reasons (APG), no typeahead, invoke closes menu and restores focus BEFORE running the action. action_registry.js: path is durable identity, element re-resolved at run time, empty context opens no menu, actions own their error UX. inline_edit.js: stem-only preselect, Escape-marks-cancel-before-blur, re-mounts across innerHTML re-renders, closes with status if row vanished. Minimal roving-tabindex focus order for rendered tree rows. One contextmenu handler serves pointer+keyboard; right-click never changes selection or fetches preview. Register real rename/trash descriptors (disabled with reasons = the Phase 1 deliverable). Port settings gear; delete its scoped display CSS and private listeners. Node DOM tests per module; design-system doc section.
