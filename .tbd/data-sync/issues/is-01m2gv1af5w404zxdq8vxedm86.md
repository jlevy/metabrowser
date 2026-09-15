---
type: is
id: is-01m2gv1af5w404zxdq8vxedm86
title: Catalog sort and Recent pass hold the GIL without cooperative yields during a walk
kind: task
status: open
priority: 2
version: 2
labels:
  - performance
dependencies: []
created_at: 2026-09-14T20:51:44.740Z
updated_at: 2026-09-14T23:50:58.345Z
---
Two whole-index passes that overlap the inventory walk still hold the GIL without a cooperative yield.

Found in the PR #122 review (R4): the catalog read's filtering loop now yields every 1,024 entries, but the sort that follows it does not; for the browser's `/api/catalog` read on a 300,000-file tree the sort took 81-169 ms of CPU. The Recent pass (`_recent_projection`) has no yields either. Neither is new in #122.

Measure first (engine performance model: counts before times), then bound or yield: e.g. sort keys precomputed and a chunked merge with cooperative yields, or a bounded top-N selection for Recent, with a deterministic work-between-yields test like tests/test_inventory_walk_work.py.

## Notes

Measured on a quiet 4-CPU Linux host (load 0.7), CPython 3.13.12, against the 300,000-file build_corpus (shape 2), settled index, v0.9.1 wheel vs main 03fd7997, each pass repeated three times while /api/index/progress was polled continuously:

| request | v0.9.1 first / repeat | main first / repeat | progress max v0.9.1 | progress max main |
| --- | --- | --- | --- | --- |
| /api/catalog | 663 / 477 / 193 ms | 2575 / 938 / 199 ms | 475 ms | 883 ms |
| /api/recent?limit=5000 | 174 / 165 / 166 ms | 420 / 428 / 435 ms | 92 ms | 110 ms |
| /api/tree?depth=0 (full tally) | 3794 / 21 / 20 ms | 4610 / 3 / 3 ms | 71 ms | 71 ms |

So the starvation this bead names is real and larger than the 81-169 ms the architecture doc records for the sort: an unrelated request waits up to 883 ms during a browser catalog read. The sort is not where it lives. Priced in isolation at 300k rows on the same host:

- CatalogRecord construction, 300k: 548 ms, of which require_canonical_inventory_path is 170 ms. The provider re-validates paths its own store admitted at discovery.
- the sort: 196 ms with key=record.path.encode('utf-8'), 124 ms with key=attrgetter('path'). UTF-8 byte order and code-point order agree, and the two orders were verified identical on 300k rows, so the encode is 72 ms and 300k bytes objects for nothing.
- _catalog_content_identity: 113 ms (71 ms if the fields are joined and hashed in chunks).
- _encode_catalog: 339 ms for a 15.9 MB body, one unbroken hold on a worker thread.
- the filtering loop already yields every 1,024 entries; the sort, the identity hash and the encode do not yield at all.

v0.9.1 answered the same request from a private list of (path, ext) tuples with no per-row contract object, no validation, no sort key encode and no content hash, which is the whole 663 -> 2,575 ms gap.

Whether this moves a gated metric is what the exp-034 release comparison decides; these numbers are the input to that reading.
