---
type: is
id: is-01m8bmw5x7npdrwac4jk89s6cj
title: "Phase 3: a GitHub request report from the event log, through a route and metab"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/903
    at: 2026-11-26T23:08:34.748Z
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bmw71z7pc66x7vrp7dz7xf
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
hold: null
hold_until: null
created_at: 2026-11-26T10:02:03.559Z
updated_at: 2026-11-26T23:23:11.977Z
started_at: 2026-11-26T22:23:20.713Z
closed_at: 2026-11-26T23:23:11.977Z
close_reason: "Merged to main as jlevy/metabrowser#903 (68cf78a6d): GET /api/plugin/github/gh-requests. Lanes follow in mb-6719; 304-as-failure in mb-e3ur."
resolution: null
duplicate_of: null
---
From the event log's gh spans: per lane and job, request count, REST core spent (non-304), GraphQL points, 304 share, latency p50/p95, requests in flight over time, queue wait, duplicate reads, cache hits, and time to the first visible answer. A route with its metab equivalent and a golden over a synthetic event log.
