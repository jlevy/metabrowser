---
type: is
id: is-01m0hfpfe5c2qqkmxtgnem57rq
title: Folder totals panel can latch a stale higher count and never correct
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-08-21T06:21:25.816Z
updated_at: 2026-08-21T07:24:51.384Z
closed_at: 2026-08-21T07:24:51.383Z
close_reason: null
---
Observed in a real browser on PR #59 at 40df198, serving a 400k-file tree, after a burst
of adds and deletes under load: the folder Overview settled on 400,019 files and stayed
there. The filesystem held 400,000, and the server agreed -- /api/rollup returned 400,000
for the exact query shape the browser uses, repeatedly and stably. A full page reload did
not clear it.

The stale number is in the client's directory totals store:

    metabrowser.directoryTotals.get("")
    { path: "", revision: 1, state: "complete",
      totalFiles: 400019, totalBytes: 1747488822, ... }

Marked complete, so it is treated as a settled measurement rather than a placeholder.

Two separate things here, and only the second belongs to PR #59.

The drift itself is upstream, in directory_totals_store.js, which the PR does not touch
(last changed in d3f8e24). It is most likely mb-pn95 -- a dropped or overflowed batch
during heavy churn leaving the store's running total permanently high. It did not
reproduce on a small tree with a clean add-then-delete cycle, which converged correctly,
so it needs the churn.

What PR #59 adds is that the correct value was available and lost. applyBestTotals in
file_totals_panel.js picks whichever source reports more files:

    (indexedTotals.totalFiles ?? 0) >= (rollupTotals.totalFiles ?? 0) ? indexedTotals : rollupTotals

The comment above it says this is "a max over the two current sources, not a ratchet over
time: a fresh, smaller reading replaces an older one, because files really can be
deleted." That holds only while both sources keep refreshing. Each is a variable holding
its last value, so once one stops updating -- a drifted store, or a rollup projection
whose debounce has gone quiet -- the larger stale reading wins every subsequent
comparison and there is nothing to unstick it.

Worth reconsidering the tie-break. The rule exists to stop a still-pending walker
aggregate from replacing real numbers with a loading state, which is a good goal, but
"more files" is a proxy for "fresher" that fails exactly when one source is broken. The
server's rollup carries index_status and can say for itself whether it is provisional;
preferring the source that reports a settled index would keep the original benefit
without making a drifted store authoritative.
