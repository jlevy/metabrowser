---
type: is
id: is-01m82c87wf2gwme1js33t2t59y
title: "Nightly soak 2026-11-19 (run 44526255047): tests/test_nav_collapse_chrome.py:96 fails at 'phase load' on main 169496f05"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T19:38:11.711Z
updated_at: 2026-11-22T19:55:37.968Z
started_at: 2026-11-22T19:55:37.966Z
---
Nightly soak chrome (4, 4/4) on main 169496f05: AssertionError 'phase load 269', assert 1 == 0 at tests/test_nav_collapse_chrome.py:96. Intermittent across five soak repetitions; find the mechanism before the 0.13.0 candidate (no rerun-it-away). Prior related: mb-hujg.
