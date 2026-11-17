---
type: is
id: is-01m7man9fyy31fp5mmq7xg7ake
title: "CI speed: test_selected_full_wait_returns_the_settled_conditional_read[switch_pin] hung to its 60 s budget on 3.14t under xdist (run 44046980214)"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T08:41:00.158Z
updated_at: 2026-11-17T08:41:00.158Z
---
On #499 at 919cb1c0 (merged with main at the time), CI run 44046980214, job test (3.14t) id 133914998106: worker gw1 timed out and crashed while running tests/test_github_pulls.py::test_selected_full_wait_returns_the_settled_conditional_read[switch_pin]. tests/suite_workers.py StackDumps printed every stack at 55 s: the main thread waits in starlette's TestClient.post on POST /api/plugin/github/pull-refresh with wait_core (tests/test_github_pulls.py:2678 in _exercise_selected_core_wait); five metabrowser_N executor threads wait in threading.Event.wait (the test's held _read_list/_get, waiting on release); the anyio portal's event loop is idle in select. So the endpoint's core wait never completed while the held reads blocked, a load-sensitive race between the core read and the held list/status reads, seen once in 6 green-or-red xdist runs. The module is in ADMITTED_GIT_TESTS, so it is fixed, not marked serial. Read the log of job 133914998106 from the 'Timeout (0:00:55)!' line.
