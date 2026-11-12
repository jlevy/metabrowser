---
type: is
id: is-01m774rr5aw6bhfzts1qpyj3w7
title: "Layer 3: named activation paths and focus hooks"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
labels:
  - layer-3
dependencies:
  - type: blocks
    target: is-01m774rrky1bpnkwshfqy4vqrz
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:54.409Z
updated_at: 2026-11-12T17:35:09.492Z
started_at: 2026-11-12T08:27:05.835Z
closed_at: 2026-11-12T17:35:09.488Z
close_reason: "Done in 674fe930 and f168ccae: selectPreviewTab extracted from initTabs and shared with the click and showPreviewTab, with role=tablist/tab and aria-selected; the filter trigger's toggleFilterMenu extracted from onMenuToggle, with the keymap's openFilterMenu focusing the checked row; the ref selector's mounted handle kept (button, activate focusing its filter); MetabrowserPluginHost.copyFromControl; focusRow hooks for Files (tree focusCurrent via focusFilesRow), Commits, and Pulls. Tests: tests/dom/sdk-copy-delegate-behavior.js, tree-keyboard-navigation-behavior.js (focusCurrent), git-panel-behavior.js (focusCommitRow), preview-pane-state-session.js (Files digit focuses the tree row), tests/test_shell_keymap_integration.py, and the key reveal session steps for S, M, X, W, Y, and the 2/1/3 focus hand-off."
resolution: null
duplicate_of: null
---
Design > Badge Targets > Activation. selectPreviewTab extracted from initTabs (with tablist semantics); openFilterMenu extracted from the filter bar's onMenuToggle closure with focus into the open menu; keep the source ref selector mount handle and focus its filter; MetabrowserPluginHost.copyFromControl; focusRow hooks for Files, Commits, and Pulls.
