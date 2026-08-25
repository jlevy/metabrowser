---
type: is
id: is-01m0vwjgvvhmfbq1n6v75gacpw
title: "PR #74 review 74-8: log cancellation-drain failures"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:52.016Z
updated_at: 2026-08-25T07:18:52.016Z
---
Review 5406736360. coordinator.py cancellation drains suppress provider failures without diagnostics. Log failures at debug with exc_info, document relay.result exception retrieval, and test observability.
