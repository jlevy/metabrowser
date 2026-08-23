---
type: is
id: is-01m0rbqq5z7qns1c2jy5pqrk5b
title: Move application lifecycle, watcher and SSE ownership to the coordinator
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqqh02gf2hnbz1mzbn617
  - type: blocks
    target: is-01m0rbqr7asmz6pt6vbejmzdj1
  - type: blocks
    target: is-01m0rbqrnt4bw8zs3d1acdwbbx
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:53.246Z
updated_at: 2026-08-23T23:49:04.777Z
---
Files: refactor src/metabrowser/events_route.py, watch_backends.py, events.py, server.py lifespan wiring and their lifecycle, watcher and SSE tests. Functions: build_lifespan must create the coordinator on app.state before discovery, attach the change relay before baseline work, start provider-owned discovery/watch work, pass RefreshRequest values instead of a concrete index into run_watcher, make _EventBus consume coordinator host events, and await coordinator.close on shutdown or root replacement. Replace _BusSingleton and get_or_create_bus with app-owned state. Preserve Last-Event-ID replay, scoped initial snapshots, queue bounds, overflow resync, capability updates, projection invalidation, heartbeats and per-tab isolation. Acceptance: no provider event contains StreamEvent; capture-before-baseline has no mutation gap; old-root tasks cannot publish after replacement; lifecycle and end-to-end SSE tests pass.
