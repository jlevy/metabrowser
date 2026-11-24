---
type: is
id: is-01m85nhbxt2am30f28mpg134y6
title: Chrome group probe's 40 s bound is under the sum of its own start and close bounds, and it prints nothing until it ends, so a slow run fails returncode == 0 with an empty message
kind: bug
status: closed
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/781
    at: 2026-11-24T02:20:31.401Z
labels: []
dependencies: []
created_at: 2026-11-24T02:18:11.257Z
updated_at: 2026-11-24T02:20:32.391Z
closed_at: 2026-11-24T02:20:32.390Z
close_reason: "The probe's 40 s bound was under its own bounds: two Chrome starts at 30 s each and two closes' waits (5+5 s, 3+3 s), 76 s together. It printed nothing until it ended, so a run stopped at 40 s failed returncode == 0 with an empty message; with no marker the lifecycle (64.5 s) also passed the suite's 60 s. Mechanism inferred from the code: another Chrome cannot be counted, and 42 snapshots found nothing outside the group. Measured 90 s budget, a timed_out assertion with stderr, per-step times on stderr, and a marker covering teardown, in PR #781 (open, not merged)."
resolution: null
duplicate_of: null
---
tests/test_process_group.py::test_chrome_keeps_its_processes_in_the_launched_group ran the probe (tests/dom/chrome-group-probe.mjs) under run_in_own_group(timeout_s=40). The probe starts Chrome twice, each start bounded at 30 s (START_BOUND_MS in tests/dom/chrome-session.mjs with 2 attempts; endpointTimeoutMs in launchBrowser), and each close waits for a Chrome that on a Mac does not leave promptly after SIGTERM (stopChrome: 5 s, SIGKILL, 5 s; launchBrowser: Browser.close up to 3 s, 3 s, SIGKILL). The 40 s outer bound fires before those inner bounds, and the probe wrote its JSON to stdout only at the end and nothing to stderr, so a run stopped by the outer bound failed 'assert run.returncode == 0' with the message 'run.stderr or run.stdout' empty. Also: with no timeout marker, the test's lifecycle (40 + GROUP_STOP_S 7.5 + PROFILE_TEARDOWN_S 17 = 64.5 s) exceeded the suite's 60 s default. Measured on a 10-core Mac 2026-11-23: 21 probes, 42 snapshots, no process naming the test profile outside the launched group; three at once at load ~180 took 17.6-18.1 s (8.5 s of it close waits); six at once at load 200-300 took 26.3-27.4 s. Mechanism for the reported failure (serif-audit, PR #777, two other Chromes running, assertion text lost) is inferred from the code, not reproduced: another Chrome cannot be counted, since _outside_the_group only considers processes naming the test's own profile.
