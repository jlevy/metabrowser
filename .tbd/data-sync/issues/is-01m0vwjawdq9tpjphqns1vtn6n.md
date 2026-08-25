---
type: is
id: is-01m0vwjawdq9tpjphqns1vtn6n
title: "PR #74 review 74-2: make read and change session mismatch semantics agree"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:45.900Z
updated_at: 2026-08-25T07:58:57.814Z
closed_at: 2026-08-25T07:58:57.814Z
close_reason: "Fixed: reads reject provider-session drift and the change relay treats it as provider failure with a host reset."
resolution: null
duplicate_of: null
---
Review 5406736360. coordinator.py _observe_read_locked currently adopts a new provider session within one handle while _publish_provider_batches resets. Choose and document one One Opened Root invariant; enforce it in tests.
