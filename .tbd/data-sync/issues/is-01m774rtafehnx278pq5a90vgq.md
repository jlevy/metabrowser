---
type: is
id: is-01m774rtafehnx278pq5a90vgq
title: "Layer 3: Help groups and closing Shift note"
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
    target: is-01m774rv75dzyrdjgrxs9erjth
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:56.621Z
updated_at: 2026-11-12T17:35:12.401Z
started_at: 2026-11-12T16:59:20.427Z
closed_at: 2026-11-12T17:35:12.400Z
close_reason: "Done in 0b2c063c and 9af41e01: View tabs (16), Controls (18), and Filters (19) groups with their context sentences; Help ends with 'Press Shift to see relevant shortcut reminders.' with Shift rendered by appendKey(); the strip renders the live reveal surface into a reminder-only second layer while revealed. Tests: tests/dom/keyboard-help-behavior.js (note, reveal layer, coalesced N or P, no strip work at rest), tests/dom/key-reveal-session.js help groups per step, golden cli-ui-key-reveal.tryscript.md."
resolution: null
duplicate_of: null
---
Design > Help Changes. Keys without Shift or Cmd; Main tabs context 'Available outside text fields.'; view-tabs, controls, filters groups; closing note 'Press Shift to see relevant shortcut reminders.' rendered with appendKey.
