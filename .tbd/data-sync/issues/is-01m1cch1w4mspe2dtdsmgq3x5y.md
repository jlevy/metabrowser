---
type: is
id: is-01m1cch1w4mspe2dtdsmgq3x5y
title: "Flaky: test_console_entry_point_survives_repeated_interrupts fails under CI load"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-31T17:05:32.034Z
updated_at: 2026-08-31T17:05:32.034Z
---
tests/test_cli_main.py::test_console_entry_point_survives_repeated_interrupts failed on all three Python versions in one CI run on PR #90 (run 33417171780) and passed on re-run of the same commit. Assertion: stderr.count('Stopping') <= 1, observed 2, at gap_s=0.0.

Not caused by that PR: its diff touches no signal handling, serve.py, or this test -- only an additive route in server.py. Passes 5/5 locally and inside the full 1678-test suite.

The race is inherent to the case the test exercises, and the test's own docstring names it: three SIGINTs with zero gap, where 'interrupts arriving back to back can cut short the write itself'. Two handlers can both reach the announcement before either sets the flag that suppresses the second. A loaded CI runner widens that window, which is why it appeared there and not locally.

Arrived with the Ctrl-C serving fix in 3160965 (PR #94). Either make the announcement idempotent under concurrent handlers -- a compare-and-set rather than a check-then-write -- or drop the gap_s=0.0 case, which is the one asserting a guarantee the implementation does not make.
