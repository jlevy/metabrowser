---
type: is
id: is-01m8bmw71z7pc66x7vrp7dz7xf
title: "Phase 3: a Pulls browsing benchmark, deterministic in CI and live against real repositories"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8bmw86vqvtr7xy5576284rf
  - type: blocks
    target: is-01m83x4y23jrcyyy2bn0ez7jm8
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
created_at: 2026-11-26T10:02:04.735Z
updated_at: 2026-11-26T10:02:07.157Z
---
A scripted session (open the Pulls tab, scroll, open several pull requests, switch tabs, revisit) against the fake gh with recorded latencies, asserting invariants: visible work before background, concurrency within its bounds, no redundant reads, a revisit served from cache, spend under a stated bound. The same session live against this repository and a large public one, recorded durably in explorations/performance-loop, including mb-mg37's hour of real browsing.
