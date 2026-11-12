---
type: is
id: is-01m774rwpvf8kz9xzn0c7f9avt
title: "Phase 2: diff layout toggle L"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
labels:
  - phase-2
dependencies: []
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:59.067Z
updated_at: 2026-11-12T21:33:55.924Z
started_at: 2026-11-12T21:14:58.671Z
closed_at: 2026-11-12T21:33:55.918Z
close_reason: "Done in f5576977. Tests: tests/dom/diff-layout-fit-session.js gives its fake api a shortcuts stand-in and prints L attached once (diff.layout, controls) on the chip it would select (aria-checked false), L choosing Unified then Split with the preference written, L after Split falls back choosing Split with its sideways scroll, the retarget after each draw, and asserts dispose detaches; pinned by tests/golden/cli-ui-diff-layout-fit.tryscript.md. Parity row diff.layout-key (owners diff-view.js#toggleLayout, #setLayout). Diff files, the Git commit view, and PR Changes all mount through diff/index.js render with window.metabrowser, so all get L."
resolution: null
duplicate_of: null
---
toggleLayout through setLayout, badge on the option it would select, retarget after each renderLayoutControl; diff files, commit view, and PR Changes; row diff.layout-key on diff-layout-fit-session.
