---
type: is
id: is-01m6msqxnfdpdgj9d3bykq9knv
title: Measure deferred Git hydration from the actual trusted selection boundary
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-dedicated-security
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T02:48:53.165Z
updated_at: 2026-11-05T02:49:08.276Z
started_at: 2026-11-05T02:49:08.274Z
---
Correct the Git deferred-hydration measurement boundary before using the scenario to accept navigation performance changes. The existing stock db52 capture records Date.now before point resolution and three CDP input commands, while perf.raw_fetch timestamps response completion. A deterministic chronological fixture using the actual scenario and actual recorder reproduces a pre-click completion falsely counted as obsolete success.

Capture the actual trusted target-row click and existing cumulative fetch completion count; classify subsequent raw samples by completion order. Retain zero obsolete responses, active-abort witness, concurrency and exact final selected/route/rendered assertions. Reject missing/untrusted/wrong-target input, observed counter reset and post-boundary sample loss. No runtime or recorder changes, no performance improvement claim. Apply only the reviewed capture/test files; root owns serial browser measurements and the independent transient hydration-readiness question. Require focused red/green, formatting, related harness tests and later normal full gate before delivery.
