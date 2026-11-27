---
type: is
id: is-01m8bmw4sdejvn3fx7tjgeyvpz
title: "Merge readiness phase 3: measure and tune how Pulls browsing uses gh and the GitHub API"
kind: feature
status: in_progress
priority: 2
version: 11
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/903
    at: 2026-11-26T23:08:35.655Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/914
    at: 2026-11-27T09:55:09.926Z
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8be438xa5kc27fpbd5rkbcy
child_order_hints:
  - is-01m8bmw5x7npdrwac4jk89s6cj
  - is-01m8bmw71z7pc66x7vrp7dz7xf
  - is-01m8bmw86vqvtr7xy5576284rf
  - is-01m8bz7s7dx150manw46zzg0n9
  - is-01m8c9jrfd6ghfav2pkc9mgc1e
  - is-01m8d1tffwxjb3n8tjt10m0ya5
  - is-01m8d1tgm8sqfmbrkrhevn8265
hold: null
hold_until: null
created_at: 2026-11-26T10:02:02.413Z
updated_at: 2026-11-27T09:55:09.926Z
started_at: 2026-11-26T22:23:19.661Z
---
Owner asked 2026-11-26, as a later phase after the readiness stack. Measure every GitHub request a Pulls browsing session makes (REST core, GraphQL points, 304s, latency, concurrency, queue wait, lane: visible, attended, prefetch, background), find the bottlenecks, and make sure parallelism, throttling, prioritization of what is visible, and the cache are used well, then fix what the measurements justify. Absorbs mb-mg37's hour-long budget measurement.
