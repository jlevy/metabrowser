---
type: is
id: is-01m7hgqtwwfyr11f95dc0apthv
title: "PR #457 B1: CI no longer drives the stack walk through a real engine; the Chrome check's Mac branch runs only on a Mac"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcje01mnwqrrmfa3d3b88g
hold: null
hold_until: null
created_at: 2026-11-16T06:29:31.675Z
updated_at: 2026-11-16T06:29:35.200Z
started_at: 2026-11-16T06:29:35.199Z
---
Review B (Low), PR #457 round 2: https://github.com/jlevy/metabrowser/pull/457#pullrequestreview-5915860949. tests/test_control_chords_chrome.py:74-77 chooses the branch from sys.platform, so Linux CI asserts only that nothing is bound; no CI job runs it on a Mac. Fix (coordinator decision): tests/dom/control-chords-chrome.mjs runs the presses under Emulation.setUserAgentOverride for a Mac navigator, then on a fresh page for a Linux navigator, and the test asserts both records on every host.
