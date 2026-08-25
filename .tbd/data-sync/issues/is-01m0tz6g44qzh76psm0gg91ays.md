---
type: is
id: is-01m0tz6g44qzh76psm0gg91ays
title: "Step 7: Validate integration in a real browser and measure cost"
kind: task
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0tz6rzhc67fjtt1s523kjzz
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-24T22:45:29.347Z
updated_at: 2026-08-25T00:07:07.842Z
closed_at: 2026-08-25T00:03:09.006Z
close_reason: Real-browser behavior, bounds, yield, hydration, replacement, theme, layout, overflow, and diagnostics validation passed; measured evidence recorded in the bead.
resolution: null
duplicate_of: null
---
Files and validation surfaces: add a representative diff artifact under tests/manual-fixtures/ for multiline JavaScript/TOML, rename, long lines, no-newline markers, unequal folded runs, deferred or over-limit cases; extend tests/test_diff_browser_js.py or a focused real-browser harness only where durable automation is feasible; use mb.perf.measure/measureAsync labels in src/metabrowser/builtin_plugins/diff/diff-view.js for syntax input/call/duration evidence; record measured results for the parent-plan addendum. Browser scenarios: observe plain text before optional syntax settles, later tokens over unchanged row tints, immediate unified/split switching with no duplicate fetch or lexer calls, single-side multi-row copy, narrow horizontal overflow, sticky bars, folds, pending hydration, replacement/disposal, and both themes. Performance fixture: representative files plus several ready files near the per-file bound; verify a yield between files and record UTF-8 input, call count, and main-thread duration. Acceptance: real Chromium checks pass, captured diagnostics show at most two calls per visible hunk and no calls on layout switch, no console errors/unhandled rejections, no aggregate cap or worker is added without measured need, and evidence is precise enough for documentation reconciliation.

## Notes

Real Chromium validation passed. Manual fixture: 3 files; unified 61 token hosts/299 spans; split 56 paired rows/43 aria-hidden padding cells/326 spans; layout persisted on reload; dark tokens transparent over status tints; no console warnings/errors. At 800px browser viewport, split body measured 437px client vs 616px scroll width with overflow-x:auto and sticky top:0 file bar. Generated near-bound comparison used four modified JS files at 508,038 lexer-input bytes each and one at 528,038 bytes: exactly four enhanced and the over-limit file remained plain; observed serialized transitions from 2 to 4 enhanced files over 74ms, with stable text and token counts across layout reprojection. Generated 55-file comparison showed 50 ready + 5 deferred at 365ms; hydration completed by 382ms while enhancement advanced file-by-file to all 55 at 750ms. Replacement at 187ms with 5 requests pending left one 5-file root, no progress, no late mutation, and no console errors. DOM tests assert the profiler emits one diffSyntax:file span with input_bytes/hunk_count/lexer_calls and one diffSyntax:lexer span per actual call.
