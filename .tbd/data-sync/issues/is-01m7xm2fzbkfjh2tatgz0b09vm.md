---
type: is
id: is-01m7xm2fzbkfjh2tatgz0b09vm
title: Nested pytest-timeout probe loses its test frame from the stack dump under CI load
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-20T23:18:39.851Z
updated_at: 2026-11-20T23:18:39.851Z
---
Observed on Metabrowser #680 at a2f3d70c, Linux CPython 3.13.14, CI run 44834917928 job 136628751079. In tests/test_suite_workers.py:96, test_a_budget_the_run_gives_is_read_as_pytest_timeout_reads_it[PYTEST_TIMEOUT] saw exactly one expected 2-second diagnostic, but its captured stack did not show probe_a_test_that_nears_a_run_budget. The nested pytest returned zero. The assertion truncated the captured stack, so the phase that emitted the dump is unknown. The outer test took 12.29 s. The worker regression file passed on that job and the previously failing Markdown golden passed separately.

Related mb-m115 and PR #569 added an untimed warmup to avoid consuming the first timed probe in autouse fixture setup under load. This run already contains that warmup, and the failing test covers the environment-budget variant. Keep the result from one retry. If it recurs, print the full nested log on a missing probe frame and measure setup, call, and teardown around the dump on Linux 3.13 under parallel load. Isolate the timed probe or run the load-sensitive case serially if measurements show contention. Keep the timeout-precedence assertion and the stack-frame check.

Evidence: https://github.com/jlevy/metabrowser/actions/runs/44834917928/job/136628751079
