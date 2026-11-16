---
type: is
id: is-01m7h20ejjc6m1k0n1vyg6dkxp
title: "PR #449 C1: the one run timeout stands even when the listing would have finished in time (504)"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h1z1rnzfafwf740k7yrzdh
hold: null
hold_until: null
created_at: 2026-11-16T02:12:05.329Z
updated_at: 2026-11-16T02:53:21.327Z
started_at: 2026-11-16T02:53:20.984Z
closed_at: 2026-11-16T02:53:21.326Z
close_reason: C1 fixed in 9d7578df6 (half the read deadline for the one run)
resolution: null
duplicate_of: null
---
Severity: Medium. PR #449 (https://github.com/jlevy/metabrowser/pull/449), review https://github.com/jlevy/metabrowser/pull/449#pullrequestreview-5914224032. References: src/metabrowser/diff/adapters/git.py:647-648, :630-631; tests/test_diff_one_run.py:391-417. See the review for the full finding and suggested fix.
