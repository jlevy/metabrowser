---
type: is
id: is-01kzcps136yjnxveym4mk45cpq
title: "Flaky under load: test_tick_does_not_block_event_loop exceeds 50ms stall limit"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-06T23:33:15.494Z
updated_at: 2026-08-11T16:57:07.569Z
closed_at: 2026-08-11T16:57:07.569Z
close_reason: Duplicate of mb-087n, which predates this report and tracks the same load-sensitive event-loop timing assertion.
---
tests/test_active_tracker_event_loop_stall.py::test_tick_does_not_block_event_loop fails during full-suite runs on slower/loaded hosts (observed 61-75ms vs 50ms limit in a cloud container) but passes 3/3 in isolation. Reproduced on a pristine tree (no local changes), so it is pre-existing. The test's own message suggests wrapping the per-entry sync glob() + check_pid_alive() loop in asyncio.to_thread; alternatively the threshold needs headroom or a load-aware skip.
