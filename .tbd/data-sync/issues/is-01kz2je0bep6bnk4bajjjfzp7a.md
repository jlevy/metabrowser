---
type: is
id: is-01kz2je0bep6bnk4bajjjfzp7a
title: Flaky event-loop stall test under full-suite load
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-03T01:04:55.662Z
updated_at: 2026-08-03T01:04:55.662Z
---
tests/test_active_tracker_event_loop_stall.py::test_tick_does_not_block_event_loop fails intermittently when the whole suite runs (observed 52-74ms against a 50ms limit). Reproduced on a clean tree at 18b40a2 in 2 of 3 full-suite runs; passes consistently standalone. The limit is load-sensitive rather than the code regressing, so the threshold or the measurement needs to tolerate a loaded CI container.
