---
type: is
id: is-01m6fgs5g0vfbktaz6y2dz9ttx
title: "PR #281 C2: the exemption from MAX_PULL_JOBS is one job per attended switch"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6fgs20qmf639pkqec7tzk5q
created_at: 2026-11-03T01:36:04.608Z
updated_at: 2026-11-03T02:16:39.481Z
closed_at: 2026-11-03T02:16:39.480Z
close_reason: "fixed in 8f5957dd: the attended may run one over, not one per switch; test_the_attended_pull_request_may_run_one_over_the_bound_and_no_more"
resolution: null
duplicate_of: null
---
Low. mirror_refresh.py:743-752. Review https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5745898115
