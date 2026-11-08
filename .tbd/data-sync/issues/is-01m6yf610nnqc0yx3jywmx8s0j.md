---
type: is
id: is-01m6yf610nnqc0yx3jywmx8s0j
title: Investigate large Source continuation and view-switch stalls
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
created_at: 2026-11-08T20:56:45.332Z
updated_at: 2026-11-08T20:56:45.332Z
---
During the installed c3 authored SDK 0.7 sample check, a public 40,000-line 2.8 MB file loads initially at 512 KB, then 2 MB and the remainder. Complete source has all 40,000 numbered rows in order and removes both Load more controls. Current built-in-browser perf diagnostics recorded an 18,704 ms main-thread block after continuation; returning Card to Source also coincided with a long command deadline. The host was concurrently running the required QA gate, and a large accessibility export timed out, so isolate product rendering, inspection overhead, and host load before assigning cause or accepting a performance result. Stable complete Source copy succeeds with exact 2,960,074-character payload. Preserve original tool timeouts and warning; first measure a few hypotheses using existing performance techniques, then choose the smallest proven fix with focused regression and before/after browser evidence. Do not increase hard limits, create a new measurement framework, or call this a release qualification. Evidence: authored SDK c3 fixture and browser artifacts from November 8.
