---
type: is
id: is-01m0vsd8dnak6hw2b87x5awch6
title: Integrate continuous scroll paging with virtualized Git history
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
labels:
  - release:v0.9.0
dependencies:
  - type: blocks
    target: is-01m0vsdfqzprgm8x1pmmgw701g
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:23:33.811Z
updated_at: 2026-08-26T23:52:50.472Z
---
Remove the user-visible row cutoff and connect bidirectional session paging, page replay, cache eviction, and virtual-window movement until Git reports the real end. Preserve scroll anchoring while pages and segments change; expose loading, retry, stale/expired-session recovery, empty, and true end-of-history states; keep tab refresh, HEAD changes, selection, direct routes, and keyboard boundary navigation deterministic.
