---
type: is
id: is-01m0vwjgvvhmfbq1n6v75gacpw
title: "PR #74 review 74-8: log cancellation-drain failures"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:52.016Z
updated_at: 2026-08-25T07:58:59.601Z
closed_at: 2026-08-25T07:58:59.600Z
close_reason: "Fixed: cancellation drains and completed relay cleanup account for provider failures in debug logs without replacing caller cancellation."
resolution: null
duplicate_of: null
---
Review 5406736360. coordinator.py cancellation drains suppress provider failures without diagnostics. Log failures at debug with exc_info, document relay.result exception retrieval, and test observability.
