---
type: is
id: is-01m6y2aa5f1yyw84wr9mxbvz78
title: Diagnose native Chrome keyboard stall and restore final browser coverage
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m3wgefqnj91f8avyyv4x8t5w
parent_id: is-01m3wgefqnj91f8avyyv4x8t5w
created_at: 2026-11-08T17:11:54.286Z
updated_at: 2026-11-08T17:12:01.500Z
---
The final 396-job functional browser differential at immutable control6c278f3f (published0.11.0) versus exact candidate426 stopped after 90 complete and 2 partial control jobs, before any candidate jobs. Wide/narrow light keyboard-navigation cases stalled on long.txt: Page.captureScreenshot and later Input.dispatchKeyEvent timed out. Native sampling located current hot work in Chrome/AppKit key handling; the application renderer was mostly waiting. Exact trigger remains unproven. Preserve every failed attempt and all 618 step records, console/action errors and unsettled states; do not label this noise or accept exit0 report generation. Verify collector/Chrome/server cleanup, investigate a bounded reproduction and propose a coverage-restoration protocol before restarting. No changed actions, timeouts, profile, dropped cases, or repeated performance attempt may silently replace the original run. Reference: private release evidence final-browser426-prepared-20261108T161150Z/interrupted-completeness-cleanup-receipt.json. Timing and release acceptance remain excluded.
