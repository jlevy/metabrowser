---
type: is
id: is-01m0hfnftbbthzzmkx6kz7n28n
title: Root /api/tree still costs O(index) via navigation_tallies
kind: bug
status: closed
priority: 2
version: 5
labels: []
dependencies: []
created_at: 2026-08-21T06:20:53.450Z
updated_at: 2026-08-21T07:24:51.124Z
closed_at: 2026-08-21T07:24:51.123Z
close_reason: null
---
arch-state-and-delivery.md, invariant 3: "No request path does work proportional to the
index. A rollup costs what changed; a tree request costs the subtree it returns."

The root tree request does not hold to this. /api/tree with an empty path runs
navigation_tallies, an explicit full pass over the index, gated on `not subpath`
(server.py, in api_tree). PR #59 removed the per-request parent/children rebuild from
_build_inventory_tree, which is what made subtree expands cheap, but this pass is
untouched and still scales with the index.

Measured on the PR branch at 40df198, settled index, synthetic trees, warm cache:

| files   | root /api/tree | subtree /api/tree |
| ------- | -------------- | ----------------- |
| 5,000   | 26ms           | 1.4ms             |
| 25,000  | 124ms          | 1.6ms             |
| 100,000 | 502ms          | 1.5ms             |

Clean linear scaling, roughly 5ms per 1000 files, against a 3.6KB response. The subtree
request stays flat, which is the PR's claim holding for expands.

This is not a regression from PR #59. The pass predates it (added in 8e48614, semantic
file type families) and the PR does not touch it. What is new is the document asserting
the invariant, and no test covering it -- the mutation that would catch it does not
exist. It is also the first nav request the browser makes on load, so it is on the path
the "opens instantly" claim is about.

Either bound the work (maintain the tallies incrementally, the way _children_index and
_subtree_aggregates now are), or narrow invariant 3 to say what is actually true and
record this cost under What Is Not Solved with the measurement above.

## Notes

Fixed for the repeat and multi-client case; the residual is mb-65mg.

The tallies are memoized on the index revision, and recency windows are answered by
binary search over a per-revision sorted mtime array rather than by another pass, so the
memo key carries no clock term.

Measured, settled, root /api/tree depth=1:

  100,000 entries    516ms -> 4.4ms
  400,000 entries   2726ms -> 13-17ms, stable across a clock-crossing pause

Simultaneous clients share one pass rather than each running their own, because the
computation is held under a dedicated lock: under the GIL, serializing identical work
costs nothing and saves N-1 passes.

Invariant 3 in arch-state-and-delivery.md claimed no request path does work proportional
to the index. That was false when written and is still not literally true, so it now says
"repeats" and the residual is recorded under What Is Not Solved with its measurement --
the first request after any change is still a full pass, and during a crawl the revision
moves on every write.

One thing found along the way and filed separately: the nav filter menus in an open page
freeze at whatever the crawl had reached and never refresh (mb-me9y). That is client-side
and pre-existing -- reproduced at 40df198 before any of this work -- and the server
response was verified correct while the stale menu was on screen.
