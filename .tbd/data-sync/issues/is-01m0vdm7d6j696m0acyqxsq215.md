---
type: is
id: is-01m0vdm7d6j696m0acyqxsq215
title: "H60: Re-run the exact installed-build v0.7 performance comparison"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0tybhtwqtawke90ae917np4
  - type: blocks
    target: is-01m0t7n4cdhfrv3fhd7f7vk23f
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-25T02:57:39.237Z
updated_at: 2026-08-25T02:57:50.280Z
---
After the stabilization fixes, build and install the exact candidate and compare it first with c123ae6, then with v0.6.0. Run at least five interleaved backend pairs and four visible headed-browser pairs on the same fingerprinted project corpus. Require semantic row/tally equality; less than 50 ms tally-overlap progress latency; every browser hard gate; no startup asset budget regression (at most 25 scripts and 175 KB); and report the full paint/startup ranges so cold-tail variance remains visible. Record the result as the next performance-loop experiment before CHANGELOG is finalized.
