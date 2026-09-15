---
type: is
id: is-01m2gv1af5w404zxdq8vxedm86
title: Catalog sort and Recent pass hold the GIL without cooperative yields during a walk
kind: task
status: open
priority: 2
version: 8
labels:
  - performance
dependencies: []
parent_id: is-01m2hs64m7nfagfxyf7b0hxrhr
created_at: 2026-09-14T20:51:44.740Z
updated_at: 2026-09-15T16:41:42.538Z
---
Two whole-index passes that overlap the inventory walk still hold the GIL without a cooperative yield.

Found in the PR #122 review (R4): the catalog read's filtering loop now yields every 1,024 entries, but the sort that follows it does not; for the browser's `/api/catalog` read on a 300,000-file tree the sort took 81-169 ms of CPU. The Recent pass (`_recent_projection`) has no yields either. Neither is new in #122.

Measure first (engine performance model: counts before times), then bound or yield: e.g. sort keys precomputed and a chunked merge with cooperative yields, or a bounded top-N selection for Recent, with a deterministic work-between-yields test like tests/test_inventory_walk_work.py.

## Notes

PART 1 -- SORT KEY: REJECTED. Do not propose again without re-measuring both shapes.
Best of seven, 300,000 CatalogRecord rows, key extracted from the record as the
projection does it:

  sort key                      all ASCII   exactly 1 non-ASCII   ~42% non-ASCII
  record.path.encode("utf-8")   157 ms      147 ms                160 ms
  record.path                   115 ms      144 ms                199 ms

A trade with no general winner, about 1.5% of the read either way. One non-ASCII file
collapses the 42 ms advantage to 3 ms but does NOT invert it -- inverting needs a large
share of the tree. (An intermediate correction claimed one file cost 41 ms; that was
measured on a 42% non-ASCII corpus and mislabelled. Fixed in exp-035.) The key stays
because the trade does not pay for touching a sort every catalog response depends on.

PART 2 -- CONTENT HASH: DONE. Landed in PR #129, merged at c465a5f2, the first change
after the v0.10.0 tag. _catalog_content_identity joins once per page instead of four
digest updates per record: 62 ms -> 41 ms at 300,000 rows, byte-identical digest, about
0.8% of the full /api/catalog time. Three tests in tests/test_catalog_feed_server.py,
written against the identity's documented definition rather than the implementation.

PART 3 -- REMAINING, AND THE ONLY REASON THIS BEAD IS STILL OPEN: the Recent pass holds
the GIL without cooperative yields during a walk. Nothing has measured this yet. That is
the original scope of this bead and the whole of what is left.
