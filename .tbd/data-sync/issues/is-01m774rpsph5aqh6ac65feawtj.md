---
type: is
id: is-01m774rpsph5aqh6ac65feawtj
title: "Layer 1: registry Shift and modifier rules"
kind: task
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
labels:
  - layer-1
dependencies:
  - type: blocks
    target: is-01m774rq85ps5fkhed4te4nhq4
  - type: blocks
    target: is-01m774rrky1bpnkwshfqy4vqrz
  - type: blocks
    target: is-01m774rtafehnx278pq5a90vgq
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:53.013Z
updated_at: 2026-11-12T08:03:04.151Z
started_at: 2026-11-12T07:38:05.179Z
closed_at: 2026-11-12T08:03:04.149Z
close_reason: "Layer 1 registry rules landed on claude/keys-1-registry (98c017c4, 3f2f9ad1, docs 6ca38816): Shift ignored for every key class, any stated modifier policy rejected at registration, digit precedence by key then Digit1-9, Shift with a named key left to a text field, permanent view-tabs scope below global, batch(), describeKey()/appendKey(), main-tabs context 'Available outside text fields.', and Help/strip re-rendering only on the events they show. Tests: tests/dom/keyboard-shortcuts-behavior.js (modifier rejection, US Shift+1, AZERTY, German Shift+7, remapped digits, Numpad, editable rule, view-tabs P fall-through, batch), tests/dom/keyboard-help-behavior.js (Help renders only while open, handled key does no strip work, batch reconciles once), tests/dom/search-palette-behavior.js (Shift+Up/Down in the query), tests/test_chrome_typography.py::test_single_keys_share_the_registry_keycap."
resolution: null
duplicate_of: null
---
Spec Rollout layer 1 and Design > Shift Rule Matching. Key classes with Shift ignored for letters, digits, punctuation; reject any stated modifier policy (Shift, Ctrl, Alt, Meta); digit precedence (event.key first, then event.code Digit1-9 only when nothing matched and key is not a digit); in an editable target Shift with a named key belongs to the field; the permanent view-tabs scope below global; batch(); Help and strip subscriber changes (re-render only on events they display; Help only while open); describeKey()/appendKey() single-key entry. Tests: keyboard-shortcuts-behavior.js and the rejection and precedence cases. Docs: design-system key, grammar, editable-target, row-collection sections; CHANGELOG Unreleased.
