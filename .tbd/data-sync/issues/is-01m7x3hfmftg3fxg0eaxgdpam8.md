---
type: is
id: is-01m7x3hfmftg3fxg0eaxgdpam8
title: test_a_listing_that_cannot_finish_is_refused_after_a_deadline_and_a_half took 4.97 s against 1.5-2.0 s on main
kind: bug
status: open
priority: 1
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T18:29:45.230Z
updated_at: 2026-11-20T19:00:30.750Z
started_at: 2026-11-20T18:32:21.684Z
---
main run 44788094422 (3664d4145), unit (3.14, 2/2): tests/test_diff_one_run.py:495 AssertionError: refused after 4.97 s, against two deadlines of 1 s. The stalling git script execs sleep 30 for a diff; READ_POLICY timeout_s is patched to 1.0. Expected half a deadline for the one run plus a whole one for the listing. About 3.5 s extra is unexplained: find where (spawn, kill, reap, pipe drain, or the event loop) and fix by cause.

## Notes

Root cause NOT found (2026-11-20). macOS: phases spawn 9 ms, one-run kill 0.512 s, listing kill 1.525 s, run returns 1.529 s; 24 copies under 20 CPU hogs max 1.595 s. Linux CI probe (draft PR 671, closed, branch deleted): 60 runs per job in the real xdist loadfile shard 2/2, on 3.12, 3.13 and 3.14, each timestamping spawn, kill, child exit (waitid WNOWAIT), pipe EOF, reap, with /proc fd-holder snapshot armed at +0.75 s after kill: 180 runs, max 1.538 s, snapshot never fired. Pipe-hold hypothesis (exit vs pipe EOF gap) not observed. Original 4.97 s failure on 3.14 2/2 unreproduced; no production defect shown.
