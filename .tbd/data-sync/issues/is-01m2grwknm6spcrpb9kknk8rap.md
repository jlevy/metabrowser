---
type: is
id: is-01m2grwknm6spcrpb9kknk8rap
title: "Stabilize the test suite under load: serve open race and full-suite sweep"
kind: bug
status: closed
priority: 1
version: 5
labels:
  - testing
dependencies: []
created_at: 2026-09-14T20:14:13.171Z
updated_at: 2026-11-01T16:21:24.498Z
closed_at: 2026-11-01T16:21:24.496Z
close_reason: Duplicate of mb-1qsn; what remains is the full-suite load sweep.
resolution: duplicate
duplicate_of: is-01m2gb3gpn7vcsw0as4xa243tg
---
Stabilize the test suite against machine load before v0.10.0.

make verify for PR #120 failed once at load average ~40 in tests/test_serve_open_race.py (a thread that binds the server after a 0.4 s sleep had not run before the helper's wall-clock timeout) and passed alone. Fix that test deterministically and sweep the full suite under load for other timing-sensitive tests.

## Notes

PR #123 (the two commits that missed #121) merged at 8dcc9830 with CI green; its review found one Low finding (a 102-character docstring line), fixed in 0dceb72b. Remaining under this bead: the full-suite load sweep. mb-gkde turned out not to be a load flake at all - the link enhancer took 32.3 s of CPU on an idle 4-CPU host against its 30 s bound; the fix is in PR #124.
