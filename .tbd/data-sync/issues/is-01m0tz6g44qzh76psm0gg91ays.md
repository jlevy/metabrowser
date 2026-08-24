---
type: is
id: is-01m0tz6g44qzh76psm0gg91ays
title: "Step 7: Validate integration in a real browser and measure cost"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0tz6rzhc67fjtt1s523kjzz
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-24T22:45:29.347Z
updated_at: 2026-08-24T23:46:35.887Z
---
Files and validation surfaces: add a representative diff artifact under tests/manual-fixtures/ for multiline JavaScript/TOML, rename, long lines, no-newline markers, unequal folded runs, deferred or over-limit cases; extend tests/test_diff_browser_js.py or a focused real-browser harness only where durable automation is feasible; use mb.perf.measure/measureAsync labels in src/metabrowser/builtin_plugins/diff/diff-view.js for syntax input/call/duration evidence; record measured results for the parent-plan addendum. Browser scenarios: observe plain text before optional syntax settles, later tokens over unchanged row tints, immediate unified/split switching with no duplicate fetch or lexer calls, single-side multi-row copy, narrow horizontal overflow, sticky bars, folds, pending hydration, replacement/disposal, and both themes. Performance fixture: representative files plus several ready files near the per-file bound; verify a yield between files and record UTF-8 input, call count, and main-thread duration. Acceptance: real Chromium checks pass, captured diagnostics show at most two calls per visible hunk and no calls on layout switch, no console errors/unhandled rejections, no aggregate cap or worker is added without measured need, and evidence is precise enough for documentation reconciliation.

## Notes

Preparing representative diff artifact, browser-level behavior checks, and mb.perf syntax measurements.
