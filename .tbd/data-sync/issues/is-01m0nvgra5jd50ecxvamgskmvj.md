---
type: is
id: is-01m0nvgra5jd50ecxvamgskmvj
title: "PR #66 review F1: tally fast path dies once the tree settles"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m0nvgqxqbb35etfxh3xbbkh9
created_at: 2026-08-22T23:04:58.948Z
updated_at: 2026-08-22T23:07:23.417Z
closed_at: 2026-08-22T23:07:23.416Z
close_reason: "Fixed: an unchanged revision now returns the memo without the age gate; the bound applies only when the revision has moved. Test test_a_settled_index_serves_the_memo_however_old_it_is pins it."
---
inventory.py:582,586-636,638-660. _navigation_tally_at is written only in the recompute branch; a memo HIT never refreshes it. Once the walk finishes and the revision stops moving, the memo ages past bound and navigation_tallies_fresh_within misses permanently — the fast path is dead exactly when it should always hit. Route then falls to navigation_tallies_snapshotting which does a full list(dict.values()) before discovering the revision is unchanged, discarding the copy. Measured: 5.2-5.8ms per poll, one wasted snapshot each, on a 200k index. Fix: when memo_key[0] == rollup_revision() the memo is provably current — return it without the age gate; apply the bound only when the revision has moved.
