---
type: is
id: is-01kzfe3r2xjtcrtm239extt3gv
title: Quick File catalog removals are O(n) per op
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-08T00:59:32.828Z
updated_at: 2026-08-09T17:43:17.202Z
---
Half of this landed in 16678d3; re-scoped to what remains.

DONE: the resync hole. fs.resync_required now calls knownFileCatalog.clear() and then quickFileCatalogFeed.onResync(), so coverage is refetched rather than left empty, and tests/test_quick_file_integration.py pins the clear-before-refetch order.

REMAINING: known_file_catalog.removeWithoutRevision() still scans every key in the map for each removed path, to catch directory-prefix removals. That is O(n) per op. With the catalog now complete rather than depth-2, n is the whole non-gitignored set, so a burst of change ops (a branch switch, a large delete) is O(n*m) on the UI thread and will jank an open search. Needs a prefix-aware structure or a deferred sweep.
