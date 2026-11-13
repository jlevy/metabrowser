---
type: is
id: is-01m774rq85ps5fkhed4te4nhq4
title: "Layer 1: remove Cmd, stack keys N and P, Shift-insensitive rows"
kind: task
status: closed
priority: 2
version: 8
spec_path: docs/project/specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
labels:
  - layer-1
dependencies:
  - type: blocks
    target: is-01m774rtafehnx278pq5a90vgq
  - type: blocks
    target: is-01m774rv75dzyrdjgrxs9erjth
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:53.476Z
updated_at: 2026-11-13T16:45:47.108Z
started_at: 2026-11-12T08:03:17.593Z
closed_at: 2026-11-12T08:03:22.134Z
close_reason: "Layer 1 key migrations landed on claude/keys-1-registry (98c017c4, ee9f01e5, docs 6ca38816): main-tabs tabBindings keeps only the bare digit, pulls.stack.top is N and pulls.stack.base is P in global with the same available(), pull-rows and pull-files J/K and the tree's J/K/arrows follow the Shift rule, the tree drops Shift+Up/Down for Home and End, and the Git rows ignore Shift but still reject Ctrl, Alt, and Meta. Tests: tests/dom/preview-pane-state-session.js with tests/golden/cli-ui-file-lifecycle.tryscript.md (ariaKeys 1, 2, 3; Command and Ctrl digits left to the browser; Shift+1 typing ! opens Files), tests/dom/pulls-nav-session.js with tests/golden/cli-ui-pulls-nav.tryscript.md and tests/test_pulls_nav.py (N and P with and without Shift; Shift+J/K on pull and changed-file rows move the row), tests/dom/tree-keyboard-navigation-behavior.js, tests/dom/git-panel-behavior.js, tests/dom/search-palette-behavior.js. Docs: design-system, README, reviewing-pull-requests, e2e-testing, CHANGELOG Unreleased."
resolution: null
duplicate_of: null
---
Spec Rollout layer 1. main-tabs.js tabBindings drops meta:require; main-tabs group context 'Available outside text fields.'; pulls-nav.js registerKeys: pulls.stack.top N, pulls.stack.base P; tree, Git rows, pull-rows, pull-files J/K accept Shift; tree drops Shift+Up/Down (Home/End stay); Quick Search keeps Shift+arrows for text selection. Update preview-pane-state-session.js, cli-ui-file-lifecycle golden, pulls-nav-session.js, cli-ui-pulls-nav golden, tree, git-panel, search-palette, keyboard-help tests, test_chrome_typography. Docs: design-system Main Tab Shortcuts, Canonical Key Names (drop Command row), pull stack and Pulls keys; README; reviewing-pull-requests.md; e2e-testing stack keys; CHANGELOG Unreleased entries for the released v0.12.0 keys.
