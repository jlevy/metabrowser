---
type: is
id: is-01m0hjan4m11x7zxd82a0jbmbq
title: Maintain navigation tallies per write so the first root request is bounded
kind: feature
status: open
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-08-21T07:07:24.179Z
updated_at: 2026-08-21T07:16:55.044Z
---
The root /api/tree request needs index-wide navigation tallies: extension, canonical
extension, family, preset, and recency counts over every file entry. That pass is
proportional to the index, measured at 486ms for 100,000 entries against a 3.8KB
response.

It is now memoized on the index revision, which removes the repeat and multi-tab cost --
516ms falls to 4.4ms on a settled index, and simultaneous clients share one pass. What
is left is the first request after any change, and during a crawl the revision moves on
every write, so every root refresh while scanning pays the full pass again.

Making it incremental is harder than _children_index or _subtree_aggregates, and the
reason is worth stating: the recency windows move with the wall clock rather than with a
write. A file changes recency bucket while nothing writes at all, so a purely
write-driven counter cannot stay correct.

The shape that resolves it: keep a per-revision sorted array of mtimes, split tracked
from ignored, and answer each recency window with a binary search rather than a scan.
That makes the clock-dependent part logarithmic in the entry count and lets everything
else be memoized on the revision alone, with no clock term in the key -- which also
removes the one-second bucket the current memo needs and the staleness that comes with
it.

Use array('q') rather than a list of ints; at the 500,000-file cap two Python int lists
would cost tens of megabytes where two int64 arrays cost about 8MB.

Worth doing when the first-request cost starts mattering -- a large root, or a tree under
continuous churn where the revision never settles. Measure with
devtools/bench_serving.py, whose tree rows report latency against response size for
exactly this reason.

## Notes

The root /api/tree request needs index-wide navigation tallies over every file entry:
486ms at 100,000 entries, 2.7s at 400,000, against a 3.8KB response.

Two parts of this are now done and should not be redone.

The result is memoized on the index revision, so repeat requests and simultaneous tabs
cost 4ms at 100,000 and 15ms at 400,000 instead of a full pass each.

The recency windows no longer force a pass. They were the reason the memo could not be
keyed on the revision alone -- a file changes recency bucket while nothing writes at all
-- and an early version handled that with a one-second clock bucket in the key. That
failed exactly where it was needed: at 400,000 entries the pass is slower than the
bucket, so consecutive requests always landed in different buckets and the memo never
hit. Recency is now a binary search per window over a per-revision sorted mtime array
(array('q'), two of them, tracked and ignored), which removed the clock from the key
entirely.

What is left is the first request after any change. During a crawl the revision moves on
every write, so a root refresh while scanning pays the whole pass again, and that is the
case a reader is most likely to be in.

Removing it means maintaining the counts per write rather than recomputing them, the way
_children_index already is: adjust the extension, canonical-extension, family, and preset
counters in _replace_index_entry and _pop_index_entry, and keep the mtime arrays sorted
under insertion and removal. The counters are straightforward; the sorted arrays are the
part to think about, since an arbitrary removal from a sorted array is O(n) and the
walker does many of them.

Measure with devtools/bench_serving.py, whose tree rows report latency against response
size for exactly this reason. The scan-with-a-client-attached row is where an improvement
would show.
