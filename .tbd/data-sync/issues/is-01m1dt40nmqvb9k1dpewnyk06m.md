---
type: is
id: is-01m1dt40nmqvb9k1dpewnyk06m
title: "Residual: inventory walk still 28% slower than main after the perf fixes"
kind: bug
status: in_progress
priority: 1
version: 8
labels: []
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
child_order_hints:
  - is-01m2gwtgp8rs2e4x0e77f64y8f
created_at: 2026-09-01T06:22:19.315Z
updated_at: 2026-09-15T00:49:22.067Z
---
After the two fixes in mb-0y68, the 60,000-file A/B still shows a gap:

  main    2,071 ms median
  stack   2,652 ms median   (+581 ms, +28%)

cProfile of the walk to settled on that corpus, top frames by tottime:

  0.283  0.534    64,420  dataclasses.py:1781 _replace
  0.260  0.260 1,953,529  dict.get
  0.254  0.254   125,525  <string>:2 __init__      (generated dataclass __init__)
  0.208  0.208    60,000  posix.DirEntry.stat
  0.146  0.237   248,826  contract.py require_canonical_inventory_path
  0.111  0.111 1,282,847  builtins.getattr

The shape of the residual is the double representation. Each entry is built as a
contract InventoryEntry (validated), converted to the provider's retained FsEntry
via _internal_entry, mutated one to three times with dataclasses.replace in the
walker path (python_inventory.py:3129, 3312, 3395), and converted back to
InventoryEntry on read. dataclasses.replace is generically slow: a getattr per
field plus a full __init__, which is where the 1.28M getattr and 125k generated
__init__ calls come from.

This is the same duplication the design review names as F1/mb-gwlw, showing up as
a measurable cost rather than an argument. Options, cheapest first: avoid replace
in the walker where only aggregate fields change and the path fields are already
validated; or let the provider retain one representation instead of two.

Do not attempt this without re-running the A/B: the measurement harness is
/tmp/ab.py style timing of 'metab CORPUS --api /api/index/meta' over
bench_serving's 60k synthetic corpus, three runs, median.

Related: the release revalidation in mb-afdb measures walk completion with a browser attached on a quiet machine and should settle whether this residual still holds on the final release commit.

## Notes

exp-034 (quiet host) confirms the residual is NOT fixed by #122, and is larger with a browser attached than backend-only.

Quiet 4-CPU Linux host, load average below 1.1 for every recorded run, five back-to-back pairs per corpus, v0.9.1 wheel against main 03fd7997.

300,000-file build_corpus, headed browser attached (walk_elapsed_ms): control 17,777-18,845 ms, candidate 28,852-33,022 ms; pair ratios 1.75, 1.78, 1.66, 1.64, 1.62. Every pair exceeds the release's 1.3x rule, on a quiet machine, where exp-033 measured 1.20-1.91 under load average 10-54.

Backend only, nothing attached (compare_builds index_done): control 14.86-16.68 s, candidate 18.86-19.50 s; pair ratios 1.13, 1.26, 1.24, 1.29, 1.30. So attaching a browser roughly doubles the gap, which points at the passes the browser drives rather than at the walker alone.

Consequences for the reader on that corpus: first_row_ms 293 ms median against 359 ms, crossing the 350 ms hard gate in three of five candidate runs (392, 359, 364); LCP 180 -> 416 ms; the page's last resource 22.3 s -> 35.1 s; two candidate runs recorded Long Tasks of 98 and 75 ms where v0.9.1 recorded none.

On the repository-shaped project-10 corpus the same candidate is much faster (walk 39.2 s -> 15.5 s, first rows 1,238 -> 230 ms) and passes every hard gate, so this is specific to a flat wide tree with no .gitignore.

Related measurement in mb-wpqq: on this corpus a browser catalog read costs 2,575 ms against v0.9.1's 663 ms and starves an unrelated request for up to 883 ms, which is the shape of the cost the browser adds to the walk.
