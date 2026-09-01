---
type: is
id: is-01m1dt3g761rxrv1r654c4ys6w
title: Inventory walk is 2.75x slower than main before the perf fixes
kind: bug
status: open
priority: 0
version: 1
labels: []
dependencies: []
created_at: 2026-09-01T06:22:02.458Z
updated_at: 2026-09-01T06:22:02.458Z
---
Measured on a 60,000-file synthetic corpus (bench_serving build_corpus, shape 2), timing 'metab CORPUS --api /api/index/meta' which waits for the full scan. Three runs each, median:

  main (2d920d60)                     2,071 ms
  stack as the PRs shipped it         5,690 ms   <- 2.75x slower
  stack + the two fixes in this bead  2,652 ms

Two causes, both fixed:

1. require_canonical_inventory_path cost 4.75 us per call and ran twice per InventoryEntry construction, ~248,000 times for 60k files. It built two PurePosixPath objects and ran a Python-level generator over every character to look for surrogates. Rewritten against the string: value.isascii() settles the surrogate question at 0.02 us because every surrogate is non-ASCII, and split('/') segment checks replace as_posix()+parts. 4.75 us -> 0.36 us. InventoryEntry construction 10.12 us -> 1.85 us. Equivalence proven by differential testing over 10,180 inputs including surrogates, NULs, and separator edge cases: identical verdicts and identical messages.

2. InventoryRuntime._invalidate_host_projections was registered as a coordinator invalidation listener, so it fired for every entry discovered during the initial walk. Each call did root / relative_path then invalidate_projection_path, which calls delete() on two mtime caches, and MtimeCache._cache_key is str(path.resolve()) -- a syscall. That is 45,516 resolves for 22,758 entries against caches that are empty during a first walk. On main this code was reachable only from watch_backends.py, i.e. only when the watcher observed a real change. Now skipped while the phase is DISCOVERING. Safe because these caches are mtime keyed and revalidate on read, so a stale entry is a miss, never a wrong answer.

In-process walk-to-settled on this repository (22,758 entries), 5 runs: 2,640 ms -> 1,117 ms median.
