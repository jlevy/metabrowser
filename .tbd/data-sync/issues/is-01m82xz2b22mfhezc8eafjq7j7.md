---
type: is
id: is-01m82xz2b22mfhezc8eafjq7j7
title: "PR #709 B1: the poll sees the record stale before its full read starts, and the page waits a window from its last probe ask"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82xz0pt2h9wt2hs1vexy0be
created_at: 2026-11-23T00:47:45.502Z
updated_at: 2026-11-23T01:18:57.770Z
closed_at: 2026-11-23T01:18:57.769Z
close_reason: Fixed in 24e61b4e3 (#709 review B1)
resolution: null
duplicate_of: null
---
High. pull-page.js automaticAskWait/askIfStale; pull_route.py probed_at, pull_state. https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015441482
