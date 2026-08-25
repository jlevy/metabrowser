---
type: is
id: is-01m0vsd8dnak6hw2b87x5awch6
title: Integrate continuous scroll paging with virtualized Git history
kind: task
status: open
priority: 1
version: 2
labels:
  - release:v0.8.0
dependencies:
  - type: blocks
    target: is-01m0vsdfqzprgm8x1pmmgw701g
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:23:33.811Z
updated_at: 2026-08-25T06:23:41.310Z
---
Remove the user-visible row cutoff and fetch the next bounded page near the loaded end until the repository reports completion. Coordinate one in-flight page, cache or reconstruct evicted page state, preserve scroll position while geometry changes, expose loading, retry, stale-cursor, and end-of-history states, and keep tab refresh and HEAD changes deterministic.
