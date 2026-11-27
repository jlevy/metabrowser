---
type: is
id: is-01m8bmw71z7pc66x7vrp7dz7xf
title: "Phase 3: a Pulls browsing benchmark, deterministic in CI and live against real repositories"
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/914
    at: 2026-11-27T09:55:09.169Z
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bmw86vqvtr7xy5576284rf
  - type: blocks
    target: is-01m83x4y23jrcyyy2bn0ez7jm8
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
hold: null
hold_until: null
created_at: 2026-11-26T10:02:04.735Z
updated_at: 2026-11-27T10:17:35.261Z
started_at: 2026-11-27T00:05:11.108Z
closed_at: 2026-11-27T10:17:35.261Z
close_reason: Merged to main as jlevy/metabrowser#914 (d0e0e1e9f). Live run against this repository recorded; the large public repository and mb-mg37's hour are left for the owner.
resolution: null
duplicate_of: null
---
A scripted session (open the Pulls tab, scroll, open several pull requests, switch tabs, revisit) against the fake gh with recorded latencies, asserting invariants: visible work before background, concurrency within its bounds, no redundant reads, a revisit served from cache, spend under a stated bound. The same session live against this repository and a large public one, recorded durably in explorations/performance-loop, including mb-mg37's hour of real browsing.
