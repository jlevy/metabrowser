---
type: is
id: is-01m2fg289rnx1wg0h5v73kaq4j
title: "PR #119 review R4: tick hook failure blames per-entry probes for every loop filesystem call"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2fg26ysev7mq8czs73qyrvf
created_at: 2026-09-14T08:20:46.519Z
updated_at: 2026-09-14T08:53:38.050Z
closed_at: 2026-09-14T08:53:38.048Z
close_reason: "Fixed in PR #119 at 5aeeac26: hook counter keyed by primitive, co_qualname, file:line and printed in the failure message. https://github.com/jlevy/metabrowser/pull/119#issuecomment-5661449001"
resolution: null
duplicate_of: null
---
tests/test_active_tracker_event_loop_stall.py:100-104,173-177. Key counter by primitive, caller qualname, file:line; print in failure message. PR #119.
