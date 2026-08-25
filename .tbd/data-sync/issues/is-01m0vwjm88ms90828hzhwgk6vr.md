---
type: is
id: is-01m0vwjm88ms90828hzhwgk6vr
title: "PR #74 review 74-12: make concurrent close callers await completion"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:55.495Z
updated_at: 2026-08-25T07:18:55.495Z
---
Review 5406736360. coordinator.close marks closed before drain, allowing a second close to return early. Preserve early operation rejection but make all close callers wait for one completed handle shutdown; test a forced interleaving.
