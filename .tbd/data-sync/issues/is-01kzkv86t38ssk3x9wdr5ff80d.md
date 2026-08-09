---
type: is
id: is-01kzkv86t38ssk3x9wdr5ff80d
title: "PR #22 review R10: a truncated inventory is presented as complete"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01kzkv76p2eprd181arkqfj0we
created_at: 2026-08-09T18:06:08.194Z
updated_at: 2026-08-09T18:06:08.194Z
---
events_route.py:658-665 returns {complete: true, truncated: true} when the walker hits its cap; catalog_feed.js:82-85 forwards only payload.complete and discards truncated, so the palette says 'N files' instead of reporting incomplete coverage, hiding every file beyond the cap. Fix: propagate catalog truncation into catalog/provider state so the candidate universe is complete only when complete && !truncated, or model indexed-complete and root-complete separately and expose the beyond-cap fallback.
