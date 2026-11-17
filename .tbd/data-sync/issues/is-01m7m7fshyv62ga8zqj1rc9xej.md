---
type: is
id: is-01m7m7fshyv62ga8zqj1rc9xej
title: "CI speed: under xdist a worker of test (3.12) crashed and the job then hung 30 minutes (run 44033895259 attempt 2); name the test and the hang"
kind: bug
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
child_order_hints:
  - is-01m7mc3my1hb6ax05y8wxkyg82
hold: null
hold_until: null
created_at: 2026-11-17T07:45:34.269Z
updated_at: 2026-11-17T09:06:19.200Z
started_at: 2026-11-17T08:39:11.696Z
---
On #499 at de96415af, CI run 44033895259 attempt 2, job test (3.12) (id 133878838296): 4 workers, 6606 items; at 07:08:31 '[gw3] node down: Not properly terminated', 'replacing crashed worker gw3', progress continued to 99% at 07:08:53, then nothing until the run was cancelled at 07:38. Cleanup found the controller, three workers, and an orphaned git (pid 16320). No stack dump: under xdist pytest-timeout's thread method os._exits the worker and its dump goes to the worker's discarded output, so the crash was most likely a 60 s timeout in some test, but its name was lost with the final summary. dbcfd3214 adds faulthandler_timeout = 55, which dumps every stack to the job log from a worker too, so the next occurrence names the test. Also a hung job has no timeout-minutes in Phase 1 and runs to GitHub's 360-minute default; Phase 2 (mb-oz36) adds the limits. Reproduce by rerunning #499's CI; read the faulthandler dump; fix the cause (a test, a git that waits forever, or xdist's handling of a crashed worker). Locally, a worker killed with a child left behind, and a test that times out, do not hang xdist 3.8.0.

## Notes

2026-11-17: dbcfd3214's faulthandler_timeout fired on every green run once main gained an 85 s Chrome test; 5c9365cc5 replaces it with tests/suite_workers.py StackDumps, which dumps every stack DUMP_LEAD_S before each test's own budget, so read the log for 'Timeout (0:00:' after the next crash.

2026-11-17: named. On jlevy/metabrowser#504, unit (3.12, 1/2) of run 44045094850 (head 6b95a0e35, which has dbcfd3214's stack dump) printed 'Timeout (0:00:55)!' with the main thread of gw1 in tests/test_diff_plugin_sidekick.py:258 test_a_git_failure_names_no_path_in_its_body -> _comparison (line 111) -> asyncio.run -> runners.close -> _cancel_all_tasks -> run_until_complete -> select: the loop waits forever on a task it cancelled at shutdown. Then '[gw1] node down: Not properly terminated', 'replacing crashed worker gw1', and no further output until the job's 6-minute limit. A likely candidate: GitDiffSource's listing awaits asyncio.gather(self._patch(...), answer) (src/metabrowser/diff/adapters/git.py:750); the test's _patch raises at once, gather does not cancel the textconv answer (read_textconv_named -> run_git_at git config), and asyncio.run's shutdown then waits on it. The same leg hung the same way, without the dump, in run 44037230262. Only Python 3.12 so far: 2 of 5 runs of that leg on #504.
