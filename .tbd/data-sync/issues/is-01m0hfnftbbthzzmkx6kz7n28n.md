---
type: is
id: is-01m0hfnftbbthzzmkx6kz7n28n
title: Root /api/tree still costs O(index) via navigation_tallies
kind: bug
status: open
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-08-21T06:20:53.450Z
updated_at: 2026-08-21T06:43:46.548Z
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

Measured again from the browser at 400k files, with the probe from mb-fodz, which adds
the part curl could not show: what this costs when more than one tab is open.

Single client, settled index, /api/tree?path=&depth=1:

  server-reported time: 1,960ms

Eight tabs asking for the same thing at once:

  8,557ms each, 68,459ms of total server work

The route has no validator and no shared build, so every client pays in full, and the
per-client cost then grows on top of that because the passes contend for the GIL. The
same probe against /api/tree?path=top00&depth=2 costs 9.9ms per client, so this is the
root request specifically, not the route.

For contrast, on the same index /api/rollup answers 8 simultaneous clients at 7.1ms each
and revalidates in 8ms with an empty body. The rollup route has the validator and the
retained body; the tree route has neither.

That makes the gap concrete: the first nav request on page load costs about two seconds
of server work at the design-center size, and a second tab doubles it.
