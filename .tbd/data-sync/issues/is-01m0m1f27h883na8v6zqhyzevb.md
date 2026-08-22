---
type: is
id: is-01m0m1f27h883na8v6zqhyzevb
title: "H8: root /api/tree pays a full nav-tally pass on every request during a scan"
kind: task
status: open
priority: 0
version: 2
labels: []
dependencies: []
created_at: 2026-08-22T06:10:26.160Z
updated_at: 2026-08-22T07:27:45.986Z
---
Root /api/tree costs 15 ms settled but 837-1,567 ms while the walk runs, identical bytes either way.

The mechanism, found by reading inventory.py: navigation_tallies memoizes on rollup_revision(), and that revision advances on every index write — at 256-entry emit batches and ~23k entries/s, ~90 times a second. So during a scan no request can ever hit the memo, and each root /api/tree re-runs the full O(N) tally pass in a to_thread; the docstring itself prices that pass at ~2 s at 400k entries. Settled, the memo hits and the route costs 15 ms.

Fix shape (H23): during scanning, serve the last computed tallies when younger than a staleness bound (500-1000 ms), recompute at most once per window, single-flight so concurrent pollers share one pass. The payload already carries tally_cache_status=scanning, so the client already treats these numbers as provisional — bounded staleness is inside the existing UX contract.

What remains of H8 after that lands is the GIL share taken by per-entry walker stores on the serving loop — that is mb-tip8 (H22). Batch mb-43v7 (H25, encoded-body cache) into the same change: same handler.

Add tallies-path timing to Server-Timing so the before/after is attributable in the probe.
