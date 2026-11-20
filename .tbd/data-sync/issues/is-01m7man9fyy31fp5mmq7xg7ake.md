---
type: is
id: is-01m7man9fyy31fp5mmq7xg7ake
title: "CI speed: test_selected_full_wait_returns_the_settled_conditional_read[switch_pin] hung to its 60 s budget on 3.14t under xdist (run 44046980214)"
kind: bug
status: closed
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/515
    at: 2026-11-20T17:02:21.339Z
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
child_order_hints:
  - is-01m7mdh2sdt4b490jctsys253a
hold: null
hold_until: null
created_at: 2026-11-17T08:41:00.158Z
updated_at: 2026-11-20T19:15:59.739Z
started_at: 2026-11-17T08:43:14.756Z
closed_at: 2026-11-17T22:23:17.290Z
close_reason: "Fixed by #515 (reviewed, dispositioned, green), merged to main at e3689d6f7 on 2026-11-17."
resolution: null
duplicate_of: null
extensions: {}
---
On #499 at 919cb1c0 (merged with main at the time), CI run 44046980214, job test (3.14t) id 133914998106: worker gw1 timed out and crashed while running tests/test_github_pulls.py::test_selected_full_wait_returns_the_settled_conditional_read[switch_pin]. tests/suite_workers.py StackDumps printed every stack at 55 s: the main thread waits in starlette's TestClient.post on POST /api/plugin/github/pull-refresh with wait_core (tests/test_github_pulls.py:2678 in _exercise_selected_core_wait); five metabrowser_N executor threads wait in threading.Event.wait (the test's held _read_list/_get, waiting on release); the anyio portal's event loop is idle in select. So the endpoint's core wait never completed while the held reads blocked, a load-sensitive race between the core read and the held list/status reads, seen once in 6 green-or-red xdist runs. The module is in ADMITTED_GIT_TESTS, so it is fixed, not marked serial. Read the log of job 133914998106 from the 'Timeout (0:00:55)!' line.

## Notes

2026-11-17: cause found; test model, not a product deadlock. The five held reads awaited asyncio.to_thread(release.wait), each keeping a default-executor thread until the test thread set release, which it does only after POST pull-refresh (wait_core) answers; that POST then needs one more thread for to_thread(pull_answer). The pool allows 64, but CPython's ThreadPoolExecutor can count an idle thread that is not there (a job submitted while a worker has seen its queue empty but not yet released _idle_semaphore starts a thread; the worker takes the job and the new thread counts itself idle too), so the next job starts no thread. CI dump matches exactly: metabrowser_0..4 all in Event.wait as the work item, no metabrowser_5, loop idle. One extra idle count released into the server's executor reproduces that dump on demand on 3.14 and 3.14t; with the fix the probe passes. Production's _read_list/_get await gh pipes on the loop and hold a worker only for the bounded _launched_files lookup, so a miscounted queue there waits for bounded work, not the request. Fix: held_until (poll the Event on the loop) for the family and the module's other 22 thread-held gates; new test_a_selected_core_wait_and_its_settlement_run_on_one_worker_thread (core/revoked/same_pin/switch_pin on DEFAULT_EXECUTOR_WORKERS=1, bounded join) fails all four with the old stubs. PR jlevy/metabrowser#515, head 1ca7db00a. Remaining 27 sites in 14 other modules: mb-qcqb.
