---
type: is
id: is-01m0vsd8dnak6hw2b87x5awch6
title: Integrate continuous scroll paging with virtualized Git history
kind: task
status: closed
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
labels:
  - release:v0.9.0
dependencies:
  - type: blocks
    target: is-01m0vsdfqzprgm8x1pmmgw701g
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:23:33.811Z
updated_at: 2026-08-27T06:54:24.000Z
closed_at: 2026-08-27T06:54:23.998Z
close_reason: Fixed in 1286ad1; full local gates, repeated exact-head headed 10,000-commit validation, push hooks, and all five GitHub checks pass.
resolution: null
duplicate_of: null
---
Remove the user-visible row cutoff and connect bidirectional session paging, page replay, cache eviction, and virtual-window movement until Git reports the real end. Preserve scroll anchoring while pages and segments change; expose loading, retry, stale/expired-session recovery, empty, and true end-of-history states; keep tab refresh, HEAD changes, selection, direct routes, and keyboard boundary navigation deterministic.

## Notes

Implemented continuous Git history integration on codex/unbounded-git-history after checkpoint 3d30e3a: removed the 500-row product ceiling and offset-paging path; added versioned server graph checkpoints, bounded append/replay page caching, fixed-height replay placeholders with local retry actions, stale/expired-session recovery, selection/focus/route preservation, HEAD-ref invalidation, and exact true-end state. Standard headed 10,000-commit linear corpus reached logical row 10,000 and exact ordinal 9,999 with 100 mounted rows (256 configured bound), 3.3 MiB JS heap after GC, zero blank frames, zero state divergence, zero page exceptions, and zero profiler long tasks; all quartile/bottom-to-top replays completed. The gate exposed and fixed two deterministic defects: live-walk stdout-pipe eviction now drains before reap, covered by a 10,000-commit regression; plugin asset configuration now deduplicates conventional styles.css from extra_styles after repeated headed direct-route runs found a duplicate stylesheet load could wait forever. Six consecutive post-fix headed 10,000-commit runs restored the deepest commit with exactly one comparison and one stylesheet. Focused DOM behavior and Git API/session tests passed. Fresh make verify passed with 1,595 tests, 48 golden scenarios, strict lint/type/public-hygiene/supply-chain gates, both audits, distribution inspection, eight-plugin doctor, and isolated installed-wheel/API smoke checks. Pending amended commit, push, and exact-head CI before closure.
