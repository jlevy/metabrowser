---
type: is
id: is-01m7bfctjmcx8pw6h1ds3cb2b1
title: "Flaky: Overview alignment Chrome test timed out at 40 s in CI"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T22:10:35.728Z
updated_at: 2026-11-13T23:25:16.852Z
closed_at: 2026-11-13T23:25:16.851Z
close_reason: "Squash-merged in #409: per-phase budgets from CI measurements (cold Chrome launch up to 14 s), failures name the phase, cleanup on every path."
resolution: null
duplicate_of: null
---
tests/test_folder_overview_alignment.py (from #405, on main since 50e43f93) timed out in CI on PR #407's run 43515169500, job test (3.12), 2026-11-13: "AssertionError: the measurement was stopped 40s after the test started; its stderr: ''" at tests/test_folder_overview_alignment.py:263, followed by "RuntimeError: Event loop is closed". 1 failed, 5554 passed. #407 does not touch the Overview, so this is a flake in the new test under CI load. It passed on #405's own CI.

Done when: the cause is found (Chrome launch, server start, the HTTP wait, or the five-width measurement under load), the test is robust under CI load with a measured deadline, the Event-loop-closed error at teardown is explained or fixed, and repeated runs under load pass.
