---
type: is
id: is-01m03xxachys56ym1n61t6krs0
title: "Flaky: test_tick_does_not_block_event_loop fails under full-suite load"
kind: bug
status: open
priority: 3
version: 3
labels: []
dependencies: []
created_at: 2026-08-16T00:00:28.038Z
updated_at: 2026-08-28T04:16:33.117Z
extensions:
  linear:
    id: b0453b87-1411-4b69-a101-d5f42bf89c3e
    linked_at: 2026-08-16T08:05:43.533Z
---
tests/test_active_tracker_event_loop_stall.py::test_tick_does_not_block_event_loop intermittently fails during a full randomized 'pytest tests/' run while passing in isolation and in subsequent full runs (observed 2026-08-15). It measures event-loop stall wall-clock, so it is sensitive to machine load and test ordering (pytest-randomly is active). Either give it more headroom or make the measurement robust to a loaded host.

## Notes

Observed 2026-08-28 on main (docs-only branch, Python byte-identical to main): the title's "under full-suite load" is too narrow. Running the test ALONE on an idle machine, it failed the first invocation and passed the next two:

  run 1: _tick wall-time=798.0ms  max event-loop stall=199.8ms  -> FAIL (limit 50ms)
  run 2: passed
  run 3: passed

The pattern points at cold filesystem cache rather than CPU contention: the first _tick pays real disk I/O for the per-entry glob() + check_pid_alive() over 200 trackable files, and the page cache absorbs it afterwards. That matches the failure message's own hypothesis (the per-entry sync loop blocks the loop) and means the fix -- wrapping the per-entry loop in asyncio.to_thread -- is warranted on its merits, not just to quiet a flake. A CI runner with a cold cache will hit this on every first run.

Also seen failing in the same full-suite run: test_worker_tally_pass_cooperatively_yields_to_the_event_loop (heartbeat 102ms vs 50ms limit), which passed in isolation. That one does look load-sensitive; see mb-087n.
