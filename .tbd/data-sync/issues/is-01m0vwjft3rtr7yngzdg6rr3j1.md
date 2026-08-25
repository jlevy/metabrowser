---
type: is
id: is-01m0vwjft3rtr7yngzdg6rr3j1
title: "PR #74 review 74-7: derive version cursors and recent truncation"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:50.946Z
updated_at: 2026-08-25T07:58:59.306Z
closed_at: 2026-08-25T07:58:59.305Z
close_reason: "Fixed: change cursors derive from EngineVersion and RecentProjection.truncated derives from row count and total matches."
resolution: null
duplicate_of: null
---
Review 5406736360. Remove duplicated session/sequence and recent truncation construction where practical; centralize ChangeCursor derivation from EngineVersion and RecentProjection truncation from total_matches/entries without a compatibility shim.
