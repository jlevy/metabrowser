---
type: is
id: is-01kz2je0bep6bnk4bajjjfzp7a
title: Flaky event-loop stall test under full-suite load
kind: bug
status: closed
priority: 2
version: 7
labels: []
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
created_at: 2026-08-03T01:04:55.662Z
updated_at: 2026-09-14T08:06:17.249Z
closed_at: 2026-09-14T08:06:17.248Z
close_reason: "Fixed in https://github.com/jlevy/metabrowser/pull/119: test_tick_does_not_block_event_loop no longer times the loop stall. A per-thread sys.setprofile hook on the event-loop thread counts filesystem primitive calls (os.stat, os.scandir, io.open, os.kill, ...) during two ticks and requires zero, with a companion test proving the hook sees every probe. Negative controls fail on 3.12/3.13/3.14/3.14t, including the stat-only regression the old share gate passed (4.6 ms)."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: bb3dffb2-7ca5-4e6d-8520-5f11a55eb40c
    linked_at: 2026-08-16T08:06:45.140Z
---
tests/test_active_tracker_event_loop_stall.py::test_tick_does_not_block_event_loop fails intermittently when the whole suite runs (observed 52-74ms against a 50ms limit). Reproduced on a clean tree at 18b40a2 in 2 of 3 full-suite runs; passes consistently standalone. The limit is load-sensitive rather than the code regressing, so the threshold or the measurement needs to tolerate a loaded CI container.

## Notes

Reviewed for v0.3.0. This is a pre-existing load-sensitive test-threshold issue, reproduced at v0.2.0 rather than a product regression. The complete v0.3.0 make verify run passed, including this test; keep one bead open for hardening the measurement.
