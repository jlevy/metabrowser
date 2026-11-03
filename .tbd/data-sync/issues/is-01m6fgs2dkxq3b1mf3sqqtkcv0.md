---
type: is
id: is-01m6fgs2dkxq3b1mf3sqqtkcv0
title: "PR #281 A1: a queued pull-request job holds a network slot while it waits its store turn"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6fgs20qmf639pkqec7tzk5q
created_at: 2026-11-03T01:36:01.458Z
updated_at: 2026-11-03T02:16:36.855Z
closed_at: 2026-11-03T02:16:36.853Z
close_reason: "fixed in 8f5957dd and 0c6f09a5: StoreTurn; turn before slot; mirror and attended go first, at most two in a row; tests in tests/test_mirror_companion.py and test_on_a_real_session_a_queue_of_pull_requests_delays_neither_the_mirror_nor_the_attended"
resolution: null
duplicate_of: null
---
Medium. mirror_refresh.py:493,790. Review https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5745300704
