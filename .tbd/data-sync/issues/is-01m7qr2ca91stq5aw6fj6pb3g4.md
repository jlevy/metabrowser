---
type: is
id: is-01m7qr2ca91stq5aw6fj6pb3g4
title: "test_suite_workers: a test near its budget fails under heavy load"
kind: bug
status: closed
priority: 3
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T16:33:03.816Z
updated_at: 2026-11-18T22:17:17.657Z
started_at: 2026-11-18T21:02:31.060Z
closed_at: 2026-11-18T22:17:17.656Z
close_reason: null
resolution: null
duplicate_of: null
---
tests/test_suite_workers.py::test_a_test_near_its_budget_leaves_every_stack_in_the_log failed locally (both parameters, then passed twice alone) at load average 60-115 during #527's make test, 2026-11-18. Timing-sensitive; not seen in CI yet. Make the timing robust to load or mark it serial.

## Notes

Fixed in PR #569 (merged as 87e35ed51, head 6f6d39c7c, CI green). Cause: the first test of a fresh pytest process pays the autouse fixtures' deferred imports in setup (0.7-3.5 s) and teardown (1.9-5.5 s) at load ~270; later tests 0.03 s or less. pytest-timeout and StackDumps time setup through teardown, so the first timed probe's 1 s dump fired in setup (fresh_markdown_child import) or its 6 s budget ended the worker in teardown. Fix: probe_a_first_test_that_warms_the_process (timeout(0)) runs first in each nested run, and the run-budget run selects it too. Probe sleeps unchanged: faulthandler lateness max 37 ms. Loops: whole file 30/30 (120 tests) at load 62-181; main's version failed 1 of 8 runs at load 23-98.
