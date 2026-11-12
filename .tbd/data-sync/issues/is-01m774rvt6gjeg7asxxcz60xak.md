---
type: is
id: is-01m774rvt6gjeg7asxxcz60xak
title: "Phase 2: plugin shortcut facade"
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
labels:
  - phase-2
dependencies:
  - type: blocks
    target: is-01m774rw8bt3z89kskcgm15ev1
  - type: blocks
    target: is-01m774rwpvf8kz9xzn0c7f9avt
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:58.149Z
updated_at: 2026-11-12T21:05:30.419Z
started_at: 2026-11-12T20:37:11.543Z
closed_at: 2026-11-12T21:05:30.418Z
close_reason: "Done in a8e0f84e (with the 185ec11e header tidy that pays for the eager queue). Tests: tests/dom/plugin-shortcuts-session.js pinned by tests/golden/cli-ui-plugin-shortcuts.tryscript.md (parity row plugins.shortcut-surface, owners plugin-shortcuts.js#attachShortcut and #attachShortcutRegistry); plugin-scope, heldAbove, and rank cases in tests/dom/keyboard-shortcuts-behavior.js; tests/test_keymap.py holds the served RESERVED_SHELL_KEYS and the refused letters to keymap.py; asset-order and dispatcher tests name plugin-shortcuts.js. Eager queue 233 bytes; startup scripts 50 bytes under budget."
resolution: null
duplicate_of: null
---
Design > Phase 2 Plugin Shortcut Surface. Eager mb.shortcuts.attach queue in plugin-sdk.js with measured bytes; static/plugin-shortcuts.js in shell-tools for validation, reserved-letter refusal, plugin-scope registration, arbitration, replay, detach by handle or signal; session plugin-shortcuts-session.js and golden; docs/plugins.md Keyboard Shortcuts.
