---
type: is
id: is-01m774qyepwq8bhzn81kc1bz6r
title: Server-Timing through the end of the body; WebKit-aware recorder shims
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:28.084Z
updated_at: 2026-11-12T05:48:12.842Z
---
Named Server-Timing spans (git, render, read, encode) measured through body end. perf.js: idle shim that waits for the first view and pauses on input, frame-gap detector in place of Long Tasks, region-movement shift in place of layout-shift where absent. Correct server.py:1337.
