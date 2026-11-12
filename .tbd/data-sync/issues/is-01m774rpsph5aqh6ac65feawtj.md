---
type: is
id: is-01m774rpsph5aqh6ac65feawtj
title: "Layer 1: registry Shift and modifier rules"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
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
created_at: 2026-11-12T05:47:53.013Z
updated_at: 2026-11-12T07:31:09.379Z
---
Spec Rollout layer 1 and Design > Shift Rule Matching. Key classes with Shift ignored for letters, digits, punctuation; reject any stated modifier policy (Shift, Ctrl, Alt, Meta); digit precedence (event.key first, then event.code Digit1-9 only when nothing matched and key is not a digit); in an editable target Shift with a named key belongs to the field; the permanent view-tabs scope below global; batch(); Help and strip subscriber changes (re-render only on events they display; Help only while open); describeKey()/appendKey() single-key entry. Tests: keyboard-shortcuts-behavior.js and the rejection and precedence cases. Docs: design-system key, grammar, editable-target, row-collection sections; CHANGELOG Unreleased.
