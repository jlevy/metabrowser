---
type: is
id: is-01m7m7fshyv62ga8zqj1rc9xej
title: "CI speed: under xdist a worker of test (3.12) crashed and the job then hung 30 minutes (run 44033895259 attempt 2); name the test and the hang"
kind: bug
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T07:45:34.269Z
updated_at: 2026-11-17T08:07:22.544Z
---
On #499 at de96415af, CI run 44033895259 attempt 2, job test (3.12) (id 133878838296): 4 workers, 6606 items; at 07:08:31 '[gw3] node down: Not properly terminated', 'replacing crashed worker gw3', progress continued to 99% at 07:08:53, then nothing until the run was cancelled at 07:38. Cleanup found the controller, three workers, and an orphaned git (pid 16320). No stack dump: under xdist pytest-timeout's thread method os._exits the worker and its dump goes to the worker's discarded output, so the crash was most likely a 60 s timeout in some test, but its name was lost with the final summary. dbcfd3214 adds faulthandler_timeout = 55, which dumps every stack to the job log from a worker too, so the next occurrence names the test. Also a hung job has no timeout-minutes in Phase 1 and runs to GitHub's 360-minute default; Phase 2 (mb-oz36) adds the limits. Reproduce by rerunning #499's CI; read the faulthandler dump; fix the cause (a test, a git that waits forever, or xdist's handling of a crashed worker). Locally, a worker killed with a child left behind, and a test that times out, do not hang xdist 3.8.0.

## Notes

2026-11-17: dbcfd3214's faulthandler_timeout fired on every green run once main gained an 85 s Chrome test; 5c9365cc5 replaces it with tests/suite_workers.py StackDumps, which dumps every stack DUMP_LEAD_S before each test's own budget, so read the log for 'Timeout (0:00:' after the next crash.
