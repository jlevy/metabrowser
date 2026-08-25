---
type: is
id: is-01m0tybgssytxdsdm4xtm6xn8h
title: Prevent navigation tally freshness checks from blocking the event loop
kind: bug
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m0vcqjmdqs2zhk804rgbjjm9
  - type: blocks
    target: is-01m0vdm7d6j696m0acyqxsq215
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
hold: null
hold_until: null
created_at: 2026-08-24T22:30:45.304Z
updated_at: 2026-08-25T03:21:24.376Z
started_at: 2026-08-25T03:03:15.508Z
closed_at: 2026-08-25T03:21:24.375Z
close_reason: Made navigation_tallies_fresh_within nonblocking under tally-lock contention; added a controlled 350 ms lock-hold/async-heartbeat regression test; focused tests and make verify pass.
resolution: null
duplicate_of: null
---
Release-readiness finding on main c123ae6. api_tree calls navigation_tallies_fresh_within synchronously on the asyncio thread, while that method blocks on the same threading lock held across the O(index) tally pass in a worker. A controlled 350 ms lock hold delayed a 20 ms asyncio timer until 351 ms. On large trees, concurrent root requests can freeze every server task for the duration of the tally pass. Make the freshness probe non-blocking or move/coalesce the lock wait off the event loop, and add a concurrency regression test.
