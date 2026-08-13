---
type: is
id: is-01kzwmp3cfc54f78nzrzdnbn5v
title: Build the shared modal overlay layer
kind: feature
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwmp9d6mgn76qgtpxvb70qz
  - type: blocks
    target: is-01kzwhmdc3jqvad5w25pdww804
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T04:04:33.294Z
updated_at: 2026-08-13T04:11:51.871Z
---
TDD src/metabrowser/static/overlay_layer.js and tests/dom/overlay_layer_behavior.js. Implement focusableElements(), captureBackgroundState(), restoreBackgroundState(), createDialogShell(), and createModal() behind window.MetabrowserOverlay. Own the body portal, shared labelled dialog anatomy, visible Close control, bounded body/footer, exact inert-state restoration, focus capture/containment/restoration, scrim close, registry-scoped Escape, one-modal arbitration, and complete disposal. Expose a frozen control binding that connects trigger aria-haspopup/aria-controls/aria-expanded to modal state and restores exact prior attributes when disconnected. Add shared token-only dialog primitives in static/styles.css and internal types in static/types.d.ts. Do not add a document keydown dispatcher or the anchored-menu slice.
