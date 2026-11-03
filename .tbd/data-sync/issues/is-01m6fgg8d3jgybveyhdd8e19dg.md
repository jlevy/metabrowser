---
type: is
id: is-01m6fgg8d3jgybveyhdd8e19dg
title: "PR #284 A2: comparison-cache attributes test not in ADMITTED_GIT_TESTS"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:12.674Z
updated_at: 2026-11-03T02:31:02.241Z
closed_at: 2026-11-03T02:31:02.239Z
close_reason: "A2 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: tests/test_diff_comparison_cache.py added to ADMITTED_GIT_TESTS; CI runs it on 2.43.7."
resolution: null
duplicate_of: null
---
Medium. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. comparison_cache.py:20-23, Makefile:132-140. Add the test so CI runs it on Git 2.43.7.
