---
type: is
id: is-01m2h6bz9ehf0pba4zs1ehjvmw
title: Settled navigation tally is 1.2-1.3x slower than v0.9.1 on a 300k tree
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-09-15T00:09:48.077Z
updated_at: 2026-09-15T00:09:48.077Z
---
devtools.compare_builds on the 300,000-file synthetic corpus, quiet 4-CPU host, v0.9.1 wheel against main 03fd7997, five interleaved pairs. The tally measured after the index settles (a depth-0 /api/tree read, with a second tally competing) is consistently slower:

- tally_overlap_tally_ms pair ratios 1.21, 1.22, 1.26, 1.31, 1.32; control 3598.5-3921.5 ms, candidate 4486.1-4792.0 ms.
- tally_overlap_competing_tally_max_ms pair ratios 1.21, 1.22, 1.26, 1.32, 1.33.

Neither is in the set the v0.10.0 release comparison judges (that set has the progress latency during the overlap, not the tally's own duration), so this does not block the release by the stated rule, but it is a real repeatable regression and belongs with the other whole-index pass costs.

On the repository-shaped project-10 corpus the same metric is 1.01-1.08x, so the cost scales with entry count rather than with directory count.

Same family as mb-wpqq: whole-index passes on this provider now build and validate contract objects per row where v0.9.1 read its own retained tuples. Measure the tally pass the way the catalog read was measured there before choosing a fix.
