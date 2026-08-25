---
type: is
id: is-01m0vwjft3rtr7yngzdg6rr3j1
title: "PR #74 review 74-7: derive version cursors and recent truncation"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:50.946Z
updated_at: 2026-08-25T07:18:50.946Z
---
Review 5406736360. Remove duplicated session/sequence and recent truncation construction where practical; centralize ChangeCursor derivation from EngineVersion and RecentProjection truncation from total_matches/entries without a compatibility shim.
