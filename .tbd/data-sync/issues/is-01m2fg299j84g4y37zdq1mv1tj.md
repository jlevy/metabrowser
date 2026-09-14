---
type: is
id: is-01m2fg299j84g4y37zdq1mv1tj
title: "PR #119 review S3: companion probe-detector test bypasses _tick call graph"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2fg26ysev7mq8czs73qyrvf
created_at: 2026-09-14T08:20:47.537Z
updated_at: 2026-09-14T08:53:39.395Z
closed_at: 2026-09-14T08:53:39.394Z
close_reason: "Fixed in PR #119 at 5aeeac26: companion drives _tick with inline hops and requires a detected call per log in each hop. https://github.com/jlevy/metabrowser/pull/119#issuecomment-5661449001"
resolution: null
duplicate_of: null
---
tests/test_active_tracker_event_loop_stall.py test_the_probe_detector_sees_every_tick_probe calls poll_observations/_pid_label directly; drive it through _tick with to_thread forced inline. PR #119.
