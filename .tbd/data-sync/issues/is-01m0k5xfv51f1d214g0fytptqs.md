---
type: is
id: is-01m0k5xfv51f1d214g0fytptqs
title: Collapse the per-folder /api/tree burst into what the viewport needs
kind: task
status: open
priority: 0
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:58.725Z
updated_at: 2026-08-21T23:49:24.407Z
---
Measured on the 100,000-file bench corpus (972 dirs), Chromium, cold load of /view/ with a fresh server so the scan is running.

The root render mounts 237 treeitems and 121 lazy stubs, with zero folders expanded. The idle sweep then warms those stubs one request at a time, roughly 700-900 ms apart, for as long as the scan runs -- observed still issuing /api/tree?path=top02/mid08&depth=2 at t+28.7 s. Each request itself costs 8-11 ms, so the cost is the schedule, not the response.

Two things are wrong and they are separable:

1. It is not viewport-bounded. pendingSubtreePaths() in static/app.js takes the first SUBTREE_PREFETCH_MAX_PER_SWEEP (32) stubs in DOM order from #tree-pane. The comment above it says "those are exactly the folders a reader can open next"; on a wide tree they are 121 folders the reader cannot see, most of them far below the fold.

2. It re-arms while the index is still changing. Each index-progress refresh re-renders the tree and calls scheduleSubtreePrefetch() again, so the sweep runs continuously for the length of the scan. Whether that is also why only one path is fetched per sweep is not yet established -- SUBTREE_PREFETCH_MAX_CONCURRENT is 3 and a sweep should take ~32 paths, so the observed serial one-per-sweep pattern is unexplained and worth pinning down before changing the policy.

The comment claims the sweep "never competes with the request a reader is actually waiting on". During a scan that is not true: these are the same route, the same server, and the same GIL as the walk that everything else is waiting for.

Hypotheses to test separately rather than as one change: (a) suspend the sweep while tally_cache_status is scanning; (b) bound candidates to the viewport plus a margin; (c) fix whatever serializes the sweep. Each needs its own before/after on this corpus.
