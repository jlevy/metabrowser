---
type: is
id: is-01kzwmp3cfc54f78nzrzdnbn5v
title: Build the shared modal overlay layer
kind: feature
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwmp9d6mgn76qgtpxvb70qz
  - type: blocks
    target: is-01kzwhmdc3jqvad5w25pdww804
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T04:04:33.294Z
updated_at: 2026-08-13T04:17:15.873Z
---
TDD src/metabrowser/static/overlay_layer.js and tests/dom/overlay_layer_behavior.js. Implement focusableElements(), captureBackgroundState(), restoreBackgroundState(), createDialogShell(), and createModal() behind window.MetabrowserOverlay. Require a registered closeCommandId; route visible Close, scrim, and Escape through that one descriptor, using shortcuts.present() for the button action name and representable aria-keyshortcuts. Own the body portal, shared labelled dialog anatomy, bounded body/footer, exact inert-state restoration, focus capture/containment/restoration, exclusive registry-scope activation/deactivation, one-modal arbitration, and complete disposal. Accept resolveFocusFallback; close focuses the connected opening trigger then the connected consumer fallback without generic selector guesses. Expose a frozen control binding that connects trigger aria-haspopup/aria-controls/aria-expanded to modal state and restores exact prior attributes when disconnected. The consumer registers its close descriptor for component lifetime; do not add another document dispatcher or an open-time command registration. Add shared token-only dialog primitives in static/styles.css and internal types in static/types.d.ts. Do not implement the anchored-menu slice.
