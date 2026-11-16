---
type: is
id: is-01m7hgs8g6hj9vr738m50z9mtf
title: "PR #471 B1: the label module's process state leaks between in-process tests"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjw3fwhayb3tmmt9prx9m
hold: null
hold_until: null
created_at: 2026-11-16T06:30:18.373Z
updated_at: 2026-11-16T07:22:41.723Z
started_at: 2026-11-16T06:30:44.075Z
closed_at: 2026-11-16T07:22:41.722Z
close_reason: "fixed in 0ef7899: _UNKNOWN removed, pull_labels.forget() and autouse fixture; https://github.com/jlevy/metabrowser/pull/471#issuecomment-6910120734"
resolution: null
duplicate_of: null
---
Low. pull_labels.py:224, :231-250; tests/conftest.py:212-223. PR #471 Review B: https://github.com/jlevy/metabrowser/pull/471#pullrequestreview-5915813181
