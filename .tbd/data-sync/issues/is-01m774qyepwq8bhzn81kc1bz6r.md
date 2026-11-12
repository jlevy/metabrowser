---
type: is
id: is-01m774qyepwq8bhzn81kc1bz6r
title: Server-Timing through the end of the body; WebKit-aware recorder shims
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:28.084Z
updated_at: 2026-11-12T07:35:11.306Z
started_at: 2026-11-12T05:53:04.050Z
---
Named Server-Timing spans (git, render, read, encode) measured through body end. perf.js: idle shim that waits for the first view and pauses on input, frame-gap detector in place of Long Tasks, region-movement shift in place of layout-shift where absent. Correct server.py:1337.

## Notes

Implemented on claude/perf-delivery (191dd8a1 / c0c293bd / 2a682e82), draft PR. Startup headroom follow-up in progress (KPress loading to sdk-views).
