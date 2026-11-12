---
type: is
id: is-01m774rw8bt3z89kskcgm15ev1
title: "Phase 2: PR page tabs C, G, H"
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
created_at: 2026-11-12T05:47:58.602Z
updated_at: 2026-11-12T21:14:46.577Z
started_at: 2026-11-12T21:05:48.083Z
closed_at: 2026-11-12T21:14:46.576Z
close_reason: "Done in 0beabfa6. Tests: tests/dom/github-pull-page-mount-behavior.js (tabKeys) mounts the page with the production registry and plugin shortcut facade and prints C, G, and H moving the route through setTab, the same with Shift, Ctrl+G left alone, the keys waiting before the record and returning when paintHeader re-inserts the tab column, the inert stage, and disposal; pinned by tests/golden/cli-ui-github-pull-page.tryscript.md and tests/test_github_pull_page_session.py. Parity row github.pull-page-tab-keys (owner pull-page.js#attachTabKeys)."
resolution: null
duplicate_of: null
---
Conversation C, Changes G, Checks H through the page handle's setTab via exported attachTabKeys; row github.pull-page-tab-keys on the existing mount session.
