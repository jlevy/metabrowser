---
type: is
id: is-01m75d7swhecbtjsmh1bqh8xer
title: "PR #348 F4: the GraphQL structure check runs on the event loop on every call"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75d7enb9z11kt1ge773zz3r
hold: null
hold_until: null
created_at: 2026-11-11T13:37:27.440Z
updated_at: 2026-11-11T14:23:40.433Z
started_at: 2026-11-11T13:37:36.975Z
closed_at: 2026-11-11T14:23:40.432Z
close_reason: "Fixed: 505e9be9. lru_cache(maxsize=64) on _is_one_read_only_query; gql_cost.py measures 0.1 us per call."
resolution: null
duplicate_of: null
---
Review F4 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858785036): 67-131 us per call, 1.4 ms for the 25-core batch; every document is a module constant or a batch size.
