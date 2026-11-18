---
type: is
id: is-01m7qr2ca91stq5aw6fj6pb3g4
title: "test_suite_workers: a test near its budget fails under heavy load"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T16:33:03.816Z
updated_at: 2026-11-18T16:33:03.816Z
---
tests/test_suite_workers.py::test_a_test_near_its_budget_leaves_every_stack_in_the_log failed locally (both parameters, then passed twice alone) at load average 60-115 during #527's make test, 2026-11-18. Timing-sensitive; not seen in CI yet. Make the timing robust to load or mark it serial.
