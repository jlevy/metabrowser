---
type: is
id: is-01m85gfjsykk9519em1pdr41b0
title: Pull page recording runs ~226 processes in series (9 s CPU), so at load ~400 on 10 cores it passes the suite's 60 s wall budget; two of its polls had no deadline
kind: bug
status: closed
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/775
    at: 2026-11-24T00:52:26.134Z
labels: []
dependencies: []
created_at: 2026-11-24T00:49:49.882Z
updated_at: 2026-11-24T01:19:08.969Z
closed_at: 2026-11-24T01:19:08.961Z
close_reason: "Slow, never stuck: the recorder's ~226 serial processes (9 s CPU) stretch past the 60 s wall budget at load ~400 on 10 cores; every refresh job ended (longest 7.8 s), no process ran past 1.5 s. Measured 180 s budget recorded beside the marker, and _fetched's two unbounded refresh polls bounded at 50 s, in PR #775 (open, CI green, not merged)."
resolution: null
duplicate_of: null
---
tests/test_github_pull_page_session.py::test_recording_is_what_a_served_pull_request_answers ran past its 60 s pytest-timeout bound locally (seen inside settle() on claude/docs-tab-file-header at cbb9fb6, which changes no code it runs). Mechanism: the recorder makes about 226 subprocess launches one after another (75 of the fake gh, each a full Python interpreter, about 33 ms CPU; 151 of git) and about 9 s of CPU in all (3.8 s in process, 5.3 s in children), measured 2026-11-23 on a 10-core M1 Pro. CI's call is 3.7 s (run 45262863839, unit 3.14 1/2). Locally alone: 33 s at load ~320, 42 s at ~400; three copies at once at ~405 took 43-48 s; three at ~396 with an event log all passed 55 s, each stopped at a different step (lines 368, 376, 409, all in _fetched), every pull job ended (longest 7.8 s), longest process 1.45 s, no span open past 2 s. So the refresh is slow under contention, never waiting on something that does not come; settle is not implicated. Also _fetched and the poll after failed_again looped on refreshing with no deadline, so a refresh that never ended would have been ended by the run-killing thread timeout instead of failing this test.
