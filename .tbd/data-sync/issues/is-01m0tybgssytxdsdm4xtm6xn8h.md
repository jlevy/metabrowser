---
type: is
id: is-01m0tybgssytxdsdm4xtm6xn8h
title: Prevent navigation tally freshness checks from blocking the event loop
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0txqcnz6aef2rzesn4cmy5w
created_at: 2026-08-24T22:30:45.304Z
updated_at: 2026-08-24T22:30:45.304Z
---
Release-readiness finding on main c123ae6. api_tree calls navigation_tallies_fresh_within synchronously on the asyncio thread, while that method blocks on the same threading lock held across the O(index) tally pass in a worker. A controlled 350 ms lock hold delayed a 20 ms asyncio timer until 351 ms. On large trees, concurrent root requests can freeze every server task for the duration of the tally pass. Make the freshness probe non-blocking or move/coalesce the lock wait off the event loop, and add a concurrency regression test.
