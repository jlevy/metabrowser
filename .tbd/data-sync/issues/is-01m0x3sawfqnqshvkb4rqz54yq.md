---
type: is
id: is-01m0x3sawfqnqshvkb4rqz54yq
title: Gate regular file-view navigation in the performance loop
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0x3skec67w78kafbez3xj2d
  - type: blocks
    target: is-01m0x52zqfhdqp9jdg82p4299j
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T18:44:09.734Z
updated_at: 2026-08-25T19:07:07.052Z
closed_at: 2026-08-25T19:07:07.039Z
close_reason: Added the trusted file-views scenario, pure health gates, exact path/route/view/mount convergence, pending and blank-frame monitoring, full server/client/paint attribution, and a successful headed trading-corpus run; its measured duplicate-request finding is tracked separately as mb-v4qu.
resolution: null
duplicate_of: null
---
Files/functions: explorations/performance-loop/capture-browser.js parseArgs plus trusted file-row selection, retained-preview frame monitor, readiness convergence, and runFileViewScenario; explorations/performance-loop/run.py capture scenario choices; tests/test_browser_performance_capture.py; docs/web-performance-framework.md and explorations/performance-loop/README.md. Behavior: a headed file-views scenario warms one regular source view, exercises cold and cached selections with trusted input, records exact selected path and painted content, total and phase timings, Server-Timing, payload, blank frames, pending-state onset and clearance, Long Tasks, Long Animation Frames, exceptions, and mounted plugin ownership. It fails on a blank retained surface, stale path/view convergence, stuck aria-busy/pending state, duplicate active mounts, missing readiness attribution, or page exceptions. Acceptance: pure contract/validator tests fail before and pass after; a real fixed-corpus headed run produces the new schema and separates server, transfer/decode, assets, mount, and paint costs.
