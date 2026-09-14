---
type: is
id: is-01m2fg27yxbcd43z2ke454ej6z
title: "PR #119 review R3: tick test label assertion over-constrains pid pairing"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2fg26ysev7mq8czs73qyrvf
created_at: 2026-09-14T08:20:46.172Z
updated_at: 2026-09-14T08:53:37.364Z
closed_at: 2026-09-14T08:53:37.363Z
close_reason: "Fixed in PR #119 at 5aeeac26: labels asserted as None-free and within {0,1}; _make_workload docstring corrected; pid-pairing control passes. https://github.com/jlevy/metabrowser/pull/119#issuecomment-5661449001"
resolution: null
duplicate_of: null
---
tests/test_active_tracker_event_loop_stall.py:170-172; src/metabrowser/active_tracker.py:109-118. Assert None not in labels and labels <= {0,1}; fix stale _make_workload docstring. PR #119.
