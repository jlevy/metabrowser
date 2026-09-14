---
type: is
id: is-01m2fg28z37wcx6c8smhrkt9d5
title: "PR #119 review S2: no deterministic test for api_rollup VersionUnavailableError fallback"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2fg26ysev7mq8czs73qyrvf
created_at: 2026-09-14T08:20:47.202Z
updated_at: 2026-09-14T08:53:39.106Z
closed_at: 2026-09-14T08:53:39.104Z
close_reason: "Fixed in PR #119 at 5aeeac26: new test_rollup_falls_back_to_a_current_read_when_its_pinned_version_expires covers the pre-read branch; payload test already covers the mid-build branch. https://github.com/jlevy/metabrowser/pull/119#issuecomment-5661449001"
resolution: null
duplicate_of: null
---
src/metabrowser/server.py api_rollup fallback after build_pinned raises VersionUnavailableError. Add a route-level test injecting coordinator.refresh between checkpoint and pinned read. PR #119.
