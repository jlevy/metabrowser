---
type: is
id: is-01m7kp7qstpnem1zdnvznm2veb
title: Provider-neutral discovery signal, semantic precheck, and engine harness (R16, R18)
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
hold: null
hold_until: null
created_at: 2026-11-17T02:44:04.538Z
updated_at: 2026-11-17T08:10:56.342Z
started_at: 2026-11-17T05:40:01.237Z
closed_at: 2026-11-17T08:10:56.342Z
close_reason: Delivered in jlevy/metabrowser#503 (provider-neutral discovery record, semantic precheck, engine-only harness), CI green.
resolution: null
duplicate_of: null
---
Replace the Python log-line regex in bench_serving and the performance loop with a diagnostics field; add a cross-provider --api digest precheck; maintain the engine-only harness. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, Measuring Before and After.
