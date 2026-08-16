---
type: is
id: is-01m03xxachys56ym1n61t6krs0
title: "Flaky: test_tick_does_not_block_event_loop fails under full-suite load"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-08-16T00:00:28.038Z
updated_at: 2026-08-16T08:05:43.533Z
extensions:
  linear:
    id: b0453b87-1411-4b69-a101-d5f42bf89c3e
    linked_at: 2026-08-16T08:05:43.533Z
---
tests/test_active_tracker_event_loop_stall.py::test_tick_does_not_block_event_loop intermittently fails during a full randomized 'pytest tests/' run while passing in isolation and in subsequent full runs (observed 2026-08-15). It measures event-loop stall wall-clock, so it is sensitive to machine load and test ordering (pytest-randomly is active). Either give it more headroom or make the measurement robust to a loaded host.
