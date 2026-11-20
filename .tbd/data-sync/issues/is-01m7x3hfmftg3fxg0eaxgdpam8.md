---
type: is
id: is-01m7x3hfmftg3fxg0eaxgdpam8
title: test_a_listing_that_cannot_finish_is_refused_after_a_deadline_and_a_half took 4.97 s against 1.5-2.0 s on main
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T18:29:45.230Z
updated_at: 2026-11-20T18:41:30.579Z
started_at: 2026-11-20T18:32:21.684Z
---
main run 44788094422 (3664d4145), unit (3.14, 2/2): tests/test_diff_one_run.py:495 AssertionError: refused after 4.97 s, against two deadlines of 1 s. The stalling git script execs sleep 30 for a diff; READ_POLICY timeout_s is patched to 1.0. Expected half a deadline for the one run plus a whole one for the listing. About 3.5 s extra is unexplained: find where (spawn, kill, reap, pipe drain, or the event loop) and fix by cause.

## Notes

Root cause NOT found (2026-11-20). Ruled out on macOS: phase timings (spawn 9 ms, one-run kill at 0.512 s, listing kill at 1.525 s, asyncio.run returns 1.529 s) and 24 concurrent copies under 20 CPU hogs, max 1.595 s. Code read: no grace period, no pipe-drain wait beyond killpg SIGKILL + proc.wait(); stalling script execs sleep so kill hits the leader. CI log has no other output from the test; its 2 git processes and 0.5 s one-run timeout line match expectations, so the extra ~3.5 s sits in an unlogged phase on Linux/3.14. Next: instrument on a Linux 3.14 runner (spawn-begin/end, term-begin/end, run-returned) via a temporary CI branch.
