---
type: is
id: is-01m2fg279h4xbm8h6zm73wpem9
title: "PR #119 review R1: tick test cannot see the loop blocked waiting on off-loop work"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2fg26ysev7mq8czs73qyrvf
created_at: 2026-09-14T08:20:45.488Z
updated_at: 2026-09-14T08:53:36.756Z
closed_at: 2026-09-14T08:53:36.755Z
close_reason: "Fixed in PR #119 at 5aeeac26: liveness rendezvous (call_soon_threadsafe + 5 s deadlock-breaker wait) after poll_observations and _compute_updates, keeping the syscall hook; sync-wait controls fail, fixed code passes. https://github.com/jlevy/metabrowser/pull/119#issuecomment-5661449001"
resolution: null
duplicate_of: null
---
tests/test_active_tracker_event_loop_stall.py:89-110,131-177. The syscall hook misses sync waits on a worker (submit().result(), shared locks, time.sleep, subprocess, C-to-C calls). Fix: liveness rendezvous wrapping poll_observations (loop.call_soon_threadsafe(event.set); event.wait(5.0) deadlock breaker), keep the hook. PR #119.
