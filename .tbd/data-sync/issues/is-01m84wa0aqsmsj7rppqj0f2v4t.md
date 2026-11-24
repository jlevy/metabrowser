---
type: is
id: is-01m84wa0aqsmsj7rppqj0f2v4t
title: test_a_readers_refresh_is_never_queued_behind_a_prefetch asserts a wall-clock bound that a loaded machine exceeds
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-23T18:57:15.605Z
updated_at: 2026-11-23T18:57:15.605Z
---
tests/test_github_pulls.py::test_a_readers_refresh_is_never_queued_behind_a_prefetch failed once during #761's review-A mutation run (-n 3, load average about 373). Pull 9's refresh took 5.91 s against a 1.26 s baseline plus 2.0 s. The mutation under test did not reach this code: with _backfill_first made to raise, the test still passes, and six serial reruns at load 310-350 all passed (1.08-2.11 s behind). The cause is the test's wall-clock threshold against scheduler delay. Make the assertion causal (the reader's refresh does not wait on the prefetch's job, observed through an event or an ordering), not a time bound. Log: .claude/worktrees/fix-budget-pm/attic/timing-761A.log
