---
type: is
id: is-01m2gv1af5w404zxdq8vxedm86
title: Catalog sort and Recent pass hold the GIL without cooperative yields during a walk
kind: task
status: in_progress
priority: 2
version: 7
labels:
  - performance
dependencies: []
parent_id: is-01m2hs64m7nfagfxyf7b0hxrhr
created_at: 2026-09-14T20:51:44.740Z
updated_at: 2026-09-15T16:38:08.414Z
---
Two whole-index passes that overlap the inventory walk still hold the GIL without a cooperative yield.

Found in the PR #122 review (R4): the catalog read's filtering loop now yields every 1,024 entries, but the sort that follows it does not; for the browser's `/api/catalog` read on a 300,000-file tree the sort took 81-169 ms of CPU. The Recent pass (`_recent_projection`) has no yields either. Neither is new in #122.

Measure first (engine performance model: counts before times), then bound or yield: e.g. sort keys precomputed and a chunked merge with cooperative yields, or a bounded top-N selection for Recent, with a deterministic work-between-yields test like tests/test_inventory_walk_work.py.

## Notes

CORRECTED TWICE. Final measurement, best of seven over 300,000 CatalogRecord rows with
the key extracted from the record exactly as the projection does it:

  sort key                      all ASCII   exactly 1 non-ASCII   ~42% non-ASCII
  record.path.encode("utf-8")   157 ms      147 ms                160 ms
  record.path                   115 ms      144 ms                199 ms
  difference                    path +42ms  path +3ms             encode +38ms

PART 1 -- THE SORT KEY: LEAVE IT ALONE.
exp-034 called this a free win. It is not a saving. An intermediate correction then
called it "a cliff triggered by a single file" -- that was measured on a 42% non-ASCII
corpus and mislabelled as the single-file case. The single-file case is a TIE (3 ms).
One non-ASCII name does take away CPython's all-latin1 fast path, which is why the 42 ms
advantage collapses, but collapsing is not inverting: inversion needs a large share of
the tree to be non-ASCII.

So it is a trade with no general winner -- 42 ms on ASCII-only trees against 38 ms on a
mostly-CJK tree, about 1.5% of the read either way. The key stays because a trade that
size does not pay for touching a sort whose order every catalog response depends on, NOT
because the alternative is worse. Order is identical on all three shapes (UTF-8 preserves
code-point order; canonical paths reject surrogates).

PART 2 -- THE CONTENT HASH: READY, DEFERRED TO AFTER THE v0.10.0 TAG.
Per-page join instead of four digest updates per record: 62 ms -> 41 ms at 300,000 rows
(1.51x on that step), byte-identical digest. About 0.8% of the full /api/catalog time,
so worth taking but not a fix. Hashing the whole catalog in one buffer is slower AND
unbounded in transient memory.

Held out of v0.10.0 only because _catalog_content_identity is on the path exp-034's
captures measured, and exp-035's argument for not re-running them is that nothing on a
measured path moved. Patch and three tests reproducible from the exp-035 write-up; the
page-boundary test is the one that matters, because folding the separator into the join
drops each page's leading byte -- the bug this actually hit when first written.

PART 3 -- REMAINING, UNMEASURED: the Recent pass holding the GIL without cooperative
yields during a walk. Still the only open question in this bead.
