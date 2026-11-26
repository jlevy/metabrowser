---
type: is
id: is-01m8d4b4wmv9ckytczde13v0hb
title: Retain NetworkSlots constructor compatibility
kind: bug
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/907
    at: 2026-11-26T23:58:38.486Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/907#pullrequestreview-6081698595
    at: 2026-11-26T23:58:38.491Z
labels: []
dependencies: []
parent_id: is-01m8d3253fqnbq74axkcc43p4k
created_at: 2026-11-26T23:51:37.089Z
updated_at: 2026-11-26T23:58:51.511Z
---
PR 907 review B1. The rebased NetworkSlots replaced the exported asyncio.Semaphore-shaped constructor. Preserve both NetworkSlots() and NetworkSlots(value=2), and add a capacity check for each.

## Notes

Fixed in 3da177783 and verified with the default capacity and keyword argument test. Review B disposition is posted.
