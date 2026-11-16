---
type: is
id: is-01m7hdak6tb8vfgbetqtt5161n
title: "PR #457 A1: Help and the Shift strip advertise Ctrl+N on Windows and Linux, where it never reaches the page"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcje01mnwqrrmfa3d3b88g
hold: null
hold_until: null
created_at: 2026-11-16T05:29:52.088Z
updated_at: 2026-11-16T06:13:16.103Z
started_at: 2026-11-16T05:30:00.612Z
closed_at: 2026-11-16T06:13:16.099Z
close_reason: "fixed in 6072e01: chords registered and presented only where controlReachesPage() (macOS, iOS); register() refuses elsewhere; pinned by pulls-nav-session.js platforms and test_control_chords_chrome.py. Disposition: https://github.com/jlevy/metabrowser/pull/457#issuecomment-6908902070"
resolution: null
duplicate_of: null
---
Medium. PR #457 review A (https://github.com/jlevy/metabrowser/pull/457#pullrequestreview-5915398035). src/metabrowser/static/keyboard-shortcuts.js:303 writes Ctrl+N off macOS; src/metabrowser/static/pulls-nav.js:377-406 registers both chords with help and reveal always; tests/test_control_chords_chrome.py:79-80; docs/design-system.md:2082-2085. Coordinator decision: register and present the chords only where Control reaches the page (macOS and iOS).
