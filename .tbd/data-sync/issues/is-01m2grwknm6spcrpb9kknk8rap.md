---
type: is
id: is-01m2grwknm6spcrpb9kknk8rap
title: "Stabilize the test suite under load: serve open race and full-suite sweep"
kind: bug
status: open
priority: 1
version: 2
labels:
  - testing
dependencies: []
created_at: 2026-09-14T20:14:13.171Z
updated_at: 2026-09-14T22:03:15.585Z
---
Stabilize the test suite against machine load before v0.10.0.

make verify for PR #120 failed once at load average ~40 in tests/test_serve_open_race.py (a thread that binds the server after a 0.4 s sleep had not run before the helper's wall-clock timeout) and passed alone. Fix that test deterministically and sweep the full suite under load for other timing-sensitive tests.

## Notes

PR #121 merged at a013c4d8 (race-test rewrite). Its review follow-up (33aadade: docstrings, served-port assertion, readiness-thread join, socket cleanup) and the parity session deadlock-only timeout (408fe931: devtools/check_parity.py 30 s -> 300 s after a lint-check timeout at load ~170) missed the merge; they are on branch claude/readiness-and-parity-followups off origin/main 5a1c475c, pushed but with no PR yet.
