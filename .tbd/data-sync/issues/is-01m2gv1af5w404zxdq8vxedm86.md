---
type: is
id: is-01m2gv1af5w404zxdq8vxedm86
title: Catalog sort and Recent pass hold the GIL without cooperative yields during a walk
kind: task
status: open
priority: 2
version: 4
labels:
  - performance
dependencies: []
created_at: 2026-09-14T20:51:44.740Z
updated_at: 2026-09-15T05:28:21.277Z
---
Two whole-index passes that overlap the inventory walk still hold the GIL without a cooperative yield.

Found in the PR #122 review (R4): the catalog read's filtering loop now yields every 1,024 entries, but the sort that follows it does not; for the browser's `/api/catalog` read on a 300,000-file tree the sort took 81-169 ms of CPU. The Recent pass (`_recent_projection`) has no yields either. Neither is new in #122.

Measure first (engine performance model: counts before times), then bound or yield: e.g. sort keys precomputed and a chunked merge with cooperative yields, or a bounded top-N selection for Recent, with a deterministic work-between-yields test like tests/test_inventory_walk_work.py.

## Notes

CORRECTED by exp-035 (2026-09-15).

PART 1 -- THE SORT KEY: REJECTED, DO NOT PROPOSE AGAIN.
exp-034's prose called the sort key a free win, on the grounds that the per-row UTF-8
encode produces the same order as sorting the path directly. The order claim holds --
UTF-8 preserves code-point order, and canonical inventory paths reject surrogates
outright -- but the saving does not. Best of five over 300,000 CatalogRecord rows:

  sort key                      ASCII-only tree   one non-ASCII name present
  record.path.encode("utf-8")   151 ms            173 ms
  record.path                   117 ms            214 ms

CPython scans a sort's keys and picks a specialized comparison; an all-latin1 str key
gets a fast path that one non-ASCII filename anywhere in 300,000 rows removes for the
whole sort. The bytes key is a plain memcmp and does not care. So it is a 34 ms saving
on all-ASCII trees bought with a 41 ms loss on any tree carrying one name that is not --
a cliff triggered by a single file, for well under 1% of the catalog read. The existing
key stays. Re-measure BOTH shapes before reopening this.

PART 2 -- THE CONTENT HASH: READY, DEFERRED TO AFTER THE v0.10.0 TAG.
Joining once per page instead of four digest updates per record measures 62 ms -> 41 ms
at 300,000 rows (1.51x on that step) with a byte-identical digest. Hashing the whole
catalog in one buffer was measured too and is both slower and unbounded in transient
memory, so per-page is the form to take.

Written and tested but deliberately NOT in v0.10.0: `_catalog_content_identity` is on
the path exp-034's captures measured, and exp-035's argument for not re-running those
captures is that nothing on a measured path moved. Landing it would have falsified that.

The patch and three tests are reproducible from the exp-035 write-up: a reference test
computing the digest the documented per-record way, a test that page boundaries do not
move the identity, and a test that the framing keeps path and extension unambiguous. The
page-boundary test is the one that matters -- folding the separator into the join drops
each page's leading byte, which is the bug this actually hit when first written.

PART 3 -- REMAINING, UNMEASURED: the Recent pass holding the GIL without cooperative
yields during a walk. Nothing has measured this yet; it is the original scope of this
bead and the only part still open as a question.
