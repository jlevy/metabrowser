---
type: is
id: is-01m1dt40nmqvb9k1dpewnyk06m
title: "Residual: inventory walk still 28% slower than main after the perf fixes"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-09-01T06:22:19.315Z
updated_at: 2026-09-01T06:22:19.315Z
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
