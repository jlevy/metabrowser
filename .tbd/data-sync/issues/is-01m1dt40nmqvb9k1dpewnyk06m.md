---
type: is
id: is-01m1dt40nmqvb9k1dpewnyk06m
title: "Residual: inventory walk still 28% slower than main after the perf fixes"
kind: bug
status: open
priority: 1
version: 4
labels: []
dependencies: []
created_at: 2026-09-01T06:22:19.315Z
updated_at: 2026-09-14T16:07:38.806Z
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

Confirmed at 300k on the v0.10.0 candidate 88606b56, and now blocking v0.10.0 (exp-033, PR #120).

exp-033 ran the exact v0.9.1 wheel against the candidate on the 300,000-file build_corpus (shape 2, tree-b4ec96ce), with a 1.3x rough-cut tolerance on back-to-back pairs, on a loaded host:

- Walk with a headed browser attached (walk_elapsed_ms): pair ratios 1.39, 1.41, 1.91, reruns 1.77 and 1.20; candidate 19.3-26.2 s vs v0.9.1 11.4-16.2 s.
- Backend index_done with nothing attached (compare_builds): pair ratios 1.22, 1.13, 1.49, rerun 1.40 at load average 10; candidate 14.0-18.4 s vs 10.0-12.9 s. It repeats with the host lightly loaded, so it is not load.
- Tally-overlap progress latency (compare_builds' 200 ms budget): candidate 243.0, 254.3, 118.4, and 213.4 ms (rerun) vs v0.9.1 69.8-105.1 ms, a candidate-only miss that makes the 300k backend report valid: false. Rows and tallies are identical.
- Also in excess on 300k: first_row_ms (1.52, rerun 1.94; still inside the 350 ms gate) and transient js_heap_mb (1.33-1.35, equal post-GC heap).

On the repository-shaped project-10 corpus the candidate is faster (walk about 0.5x, index_done 0.21-0.41x), because the removed .gitignore pre-walk dominates there. The 300k tree is flat and wide with no .gitignore, so it isolates per-entry walker cost, which is where the residual below lives.

Original analysis (60k A/B after mb-0y68): main 2,071 ms vs stack 2,652 ms median (+28%). cProfile top frames by tottime: dataclasses._replace 0.283 s (64,420 calls), dict.get 0.260 s (1.95M), generated dataclass __init__ 0.254 s (125,525), DirEntry.stat 0.208 s, require_canonical_inventory_path 0.146 s (248,826), getattr 0.111 s (1.28M). The shape is the double representation: contract InventoryEntry built and validated, converted to the provider's retained FsEntry via _internal_entry, mutated one to three times with dataclasses.replace in the walker path, and converted back on read (the design review's F1, mb-gwlw). Options, cheapest first: avoid replace in the walker where only aggregate fields change and path fields are already validated; or retain one representation.

Acceptance for the fix: rerun the exp-033 comparison on the fixed commit (same v0.9.1 wheel, corpora, environments, and pair rule), with every 300k walk_elapsed_ms and index_done pair within 1.3x and the tally-overlap progress latency inside 200 ms. Re-measure the 300k first_row_ms and /api/tree server time in the same round.
