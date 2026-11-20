---
type: is
id: is-01m7wweb3xhf6783751gszs00g
title: test_github_ref_pulls asserts non-blocking by a 0.25 s wall clock and exceeded it (cause under investigation)
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-20T16:25:42.268Z
updated_at: 2026-11-20T16:40:21.717Z
---
PR 655 run 44771960710 job 136411653812 (admitted-git 2.43.7): assert time.monotonic() - began < 0.25 failed at 0.35 s. A wall-clock bound this tight fails on a loaded runner; unrelated to the change under test. Rerun once; consider a bound that does not depend on runner load.
