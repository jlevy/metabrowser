---
type: is
id: is-01m0jt3f1hdn6aqt75q7ct5bpn
title: "R5: make the recency filter cacheable via sorted mtimes and binary search"
kind: feature
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0jt1hr4r6yqhgxkv0bpyayj
created_at: 2026-08-21T18:42:31.600Z
updated_at: 2026-08-21T19:03:45.048Z
---
PR #60 review finding R5 (medium; opportunity rather than defect).

cached_rollups skips the cache entirely when recency_seconds is set, because "its verdicts
move with the clock". The reasoning is right and the escape hatch is honest. The
consequence is that the full O(index) pass runs on every request precisely when a recency
filter is on -- and by #60's own account, one filter change fans out into the tree request
plus a subtree request per lazy stub the prefetch sweep warms.

#59 hit the same problem and the fix is already in the tree. The navigation tallies had the
same clock dependency. An early version keyed the memo on a rounded second; it never hit at
400k entries, because the pass took longer than the bucket, so every request landed in a
later bucket than the one before it. Measured before that was understood: six consecutive
root requests at 400k cost 1970, 2052, 1967ms, with no reuse at all.

What worked: keep a per-revision sorted array("q") of mtimes, split tracked from ignored,
and answer each window with a binary search -- everything at or after the cutoff's
insertion point is inside the window. The memoized half then depends on the entries alone
and the key carries no clock term. See _with_recency and _NavigationTallyBase in
inventory.py on main.

Applying the same shape here would make the recency filter cacheable like every other
dimension. Not a merge blocker; worth doing before the prefetch sweep meets a large tree.

## Notes

Deferred from the PR #60 review as agreed: an opportunity, not a defect. The pattern to reuse is _with_recency in inventory.py on main — a per-revision sorted array of mtimes answered by binary search, so the memo key carries no clock term. Do it before the prefetch sweep meets a large tree: today a recency filter runs the full O(index) pass on every request in the fan-out.
