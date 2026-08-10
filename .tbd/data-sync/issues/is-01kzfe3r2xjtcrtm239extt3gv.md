---
type: is
id: is-01kzfe3r2xjtcrtm239extt3gv
title: Quick File catalog removals are O(n) per op
kind: bug
status: open
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-08-08T00:59:32.828Z
updated_at: 2026-08-10T01:31:24.759Z
---
Half of this landed in 16678d3; re-scoped to what remains.

DONE: the resync hole. fs.resync_required now calls knownFileCatalog.clear() and then quickFileCatalogFeed.onResync(), so coverage is refetched rather than left empty, and tests/test_quick_file_integration.py pins the clear-before-refetch order.

REMAINING: known_file_catalog.removeWithoutRevision() still scans every key in the map for each removed path, to catch directory-prefix removals. That is O(n) per op. With the catalog now complete rather than depth-2, n is the whole non-gitignored set, so a burst of change ops (a branch switch, a large delete) is O(n*m) on the UI thread and will jank an open search. Needs a prefix-aware structure or a deferred sweep.

## Notes

Design review 2026-08-09: tiered. Tier 1 LOW RISK ~20 lines: batch removals per applyEventChange call — collect contiguous remove prefixes and do one O(n) pass per group instead of per op, turning a branch-switch burst from O(n*m) into O(n+groups). Intra-batch ordering (remove dir, then upsert child under it) survives because groups apply in sequence.

Tier 2, only if profiling at 100k+ shows Tier 1 still janks: segment trie (nested maps keyed by path segment). Clean asymptotics, no ordering subtleties, ~1-2 days plus property tests.

REJECTED: deferred sweep (mark prefixes, filter at snapshot). Superficially free since snapshot() already pays a full sort per revision, but remove-then-upsert ordering breaks unless every entry carries a sequence number — epoch semantics smuggled in through a performance patch. Bug-breeding; do not take this path.

Perspective: at the 500k cap the dominant cost is the provider scan itself (~0.8s measured at 50k => ~8s extrapolated), not removals. Below ~100k Tier 1 suffices; past it the real answer is the deferred bounded server search (mb-3arq), not client-side data-structure work.
