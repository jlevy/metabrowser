---
type: is
id: is-01m774rq85ps5fkhed4te4nhq4
title: "Layer 1: remove Cmd, stack keys N and P, Shift-insensitive rows"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
labels:
  - layer-1
dependencies:
  - type: blocks
    target: is-01m774rtafehnx278pq5a90vgq
  - type: blocks
    target: is-01m774rv75dzyrdjgrxs9erjth
parent_id: is-01m76jgfxbadse383jypkzwpm9
created_at: 2026-11-12T05:47:53.476Z
updated_at: 2026-11-12T07:31:09.802Z
---
Spec Rollout layer 1. main-tabs.js tabBindings drops meta:require; main-tabs group context 'Available outside text fields.'; pulls-nav.js registerKeys: pulls.stack.top N, pulls.stack.base P; tree, Git rows, pull-rows, pull-files J/K accept Shift; tree drops Shift+Up/Down (Home/End stay); Quick Search keeps Shift+arrows for text selection. Update preview-pane-state-session.js, cli-ui-file-lifecycle golden, pulls-nav-session.js, cli-ui-pulls-nav golden, tree, git-panel, search-palette, keyboard-help tests, test_chrome_typography. Docs: design-system Main Tab Shortcuts, Canonical Key Names (drop Command row), pull stack and Pulls keys; README; reviewing-pull-requests.md; e2e-testing stack keys; CHANGELOG Unreleased entries for the released v0.12.0 keys.
