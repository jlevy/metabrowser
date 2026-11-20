---
type: is
id: is-01m7xjk9st46vjsnkjgg454g7j
title: SQLite reader workers fail to start watchdog threads on Linux CPython 3.14t
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
labels:
  - testing
dependencies: []
parent_id: is-01m7vtd1yhvcp2szqx4m266c1p
created_at: 2026-11-20T22:52:53.433Z
updated_at: 2026-11-20T22:52:53.433Z
---
The draft SQLite access layer fails on Linux/free-threaded CPython 3.14.6. On #674 at 5778f0d53, CI run 44817949088 passes the 3.12/3.13/3.14 unit jobs. The 3.14t jobs return `The reader failed: RuntimeError: can't start new thread` or memory-pressure errors on small fixtures, breaking test_a_worker_serves_one_subject, test_an_answer_past_the_cap_stops_its_reader, SQLite Info and pin requests, and the SQLite golden. The #675 failures inherit this behavior. The GitHub status golden and file-watch disclosure failures have separate test fixes.

Evidence: https://github.com/jlevy/metabrowser/actions/runs/44817949088/job/136572855715 and https://github.com/jlevy/metabrowser/actions/runs/44817949088/job/136572855408. First rerun with the exact 3.14.6+freethreaded Linux x86_64 build the Actions job installed. Compare current /proc/self/status VmSize at worker bootstrap, just before and after the first watchdog thread, and with/without the 1 GiB RLIMIT_AS. Also check the runner's process/thread limits. CPython's per-thread mimalloc heaps make virtual address reservation a plausible cause, unproven. Preserve a measured memory bound and both deadline checks. A runtime change needs the minimal reproduction and the original 3.14t checks passing.
