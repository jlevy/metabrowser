---
type: is
id: is-01m0rbqspkv8et5wzmchk9c5mv
title: Add the provider performance axis and compare the Python refactor
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqt1448pdt09sadn5xdpa
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:55.826Z
updated_at: 2026-08-23T22:26:56.163Z
---
Files: update devtools/bench_serving.py, explorations/performance-loop/run.py and README.md, server diagnostics/logging and tests/test_perf_instrumentation.py. Functions: record provider name and contract identity in benchmark inputs/results, server logs and diagnostics; keep old result files readable only where an actual committed artifact requires it, without speculative runtime compatibility. Run the 100000-file serving benchmark back to back against .bench/inventory-provider-before.json and capture cold scan, attached scan, first useful rows, scanning/settled rollup paths, concurrency, tree routes, CPU/memory/work counters and binding-copy values available in Phase 1. Acceptance: no unexplained regression outside measured harness noise; the same axis can select fdu in Phase 2 without changing routes or the browser.
