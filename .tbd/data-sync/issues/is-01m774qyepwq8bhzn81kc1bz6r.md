---
type: is
id: is-01m774qyepwq8bhzn81kc1bz6r
title: Server-Timing through the end of the body; WebKit-aware recorder shims
kind: task
status: closed
priority: 2
version: 6
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
updated_at: 2026-11-14T00:50:25.295Z
started_at: 2026-11-12T05:53:04.050Z
closed_at: 2026-11-14T00:50:25.294Z
close_reason: "Landed in #372 (merge 7e27e32b): Server-Timing phases and the WebKit-aware idle helper (metabrowser.whenIdle) and frame recorder. diag083 showed Server-Timing adds 0.2-0.5 ms per request and does not cause the cold JSON view's extra frame (a variant without it showed the frame in 3 of 4 runs). All idle work now goes through whenIdle, including #370's idle face load."
resolution: null
duplicate_of: null
---
Named Server-Timing spans (git, render, read, encode) measured through body end. perf.js: idle shim that waits for the first view and pauses on input, frame-gap detector in place of Long Tasks, region-movement shift in place of layout-shift where absent. Correct server.py:1337.

## Notes

Implemented on claude/perf-delivery, PR #372 (191dd8a1 / c0c293bd / 2a682e82; 640e008d moves KPress loading to sdk-views, restoring 3,062 bytes of startup headroom and regenerating the two goldens the stamps changed). Awaiting harness v2 for rounds exp-060 and exp-062.
